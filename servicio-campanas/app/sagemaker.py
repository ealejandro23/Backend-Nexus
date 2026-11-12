"""Integración con el endpoint de SageMaker del modelo de propensión.

El worker consulta SageMaker para las categorías candidatas. Si el endpoint
no está configurado o falla, usa las predicciones ya guardadas en PostgreSQL
y marca la campaña como degradada. Así la ruta de campañas sigue operativa.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from .config import Settings

logger = logging.getLogger(__name__)


def _etiqueta(probabilidad: float) -> str:
    if probabilidad >= 0.70:
        return "alta"
    if probabilidad >= 0.40:
        return "media"
    return "baja"


def _parsear_salida(data: Any, categoria: str) -> list[dict[str, Any]]:
    """Normaliza las distintas formas de respuesta de un endpoint SageMaker."""
    resultados: list[dict[str, Any]] = []

    def agregar(cat: str, valor: Any) -> None:
        try:
            prob = float(valor)
        except (TypeError, ValueError):
            return
        resultados.append(
            {
                "categoria": cat,
                "propension": round(max(0.0, min(1.0, prob)), 4),
                "propension_etiqueta": _etiqueta(prob),
                "origen": "sagemaker",
            }
        )

    if isinstance(data, dict):
        for clave in ("probabilidad", "prediccion", "score", "propension"):
            if clave in data:
                agregar(str(data.get("categoria", categoria)), data[clave])
                return resultados
        if "predictions" in data:
            return _parsear_salida(data["predictions"], categoria)
        if "result" in data:
            return _parsear_salida(data["result"], categoria)
        # Formato por categoría: {"audio": 0.71, "video": 0.32}
        for cat, valor in data.items():
            if isinstance(valor, (int, float)):
                agregar(cat, valor)
        return resultados

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                cat = str(item.get("categoria", categoria))
                for clave in ("probabilidad", "prediccion", "score"):
                    if clave in item:
                        agregar(cat, item[clave])
                        break
            elif isinstance(item, (int, float)):
                agregar(categoria, item)
        return resultados

    if isinstance(data, (int, float)):
        agregar(categoria, data)
    return resultados


class SageMakerRecommender:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Any = None

    def _runtime(self) -> Any:
        if self._client is None:
            import boto3  # import perezoso para que los tests no lo necesiten

            self._client = boto3.client(
                "sagemaker-runtime", region_name=self.settings.aws_region
            )
        return self._client

    def _admin(self) -> Any:
        import boto3

        return boto3.client("sagemaker", region_name=self.settings.aws_region)

    async def health(self) -> tuple[str, str, float]:
        inicio = time.monotonic()
        if not self.settings.sagemaker_endpoint_name:
            return "no_configurado", "SAGEMAKER_ENDPOINT_NAME no configurado", 0.0

        def _describe() -> str:
            respuesta = self._admin().describe_endpoint(
                EndpointName=self.settings.sagemaker_endpoint_name
            )
            return str(respuesta.get("EndpointStatus", "Desconocido"))

        try:
            estado = await asyncio.wait_for(
                asyncio.to_thread(_describe),
                timeout=self.settings.health_timeout_seconds,
            )
        except asyncio.TimeoutError:
            return "error", "timeout al consultar SageMaker", (time.monotonic() - inicio) * 1000
        except Exception as exc:  # botocore, credenciales, red, etc.
            return "error", f"{type(exc).__name__}: {exc}", (time.monotonic() - inicio) * 1000

        latencia = (time.monotonic() - inicio) * 1000
        if estado == "InService":
            return "ok", f"endpoint {self.settings.sagemaker_endpoint_name} InService", latencia
        return "degradado", f"endpoint en estado {estado}", latencia

    async def recomendar(
        self,
        usuario_id: str,
        perfil_raw: dict[str, Any],
        predicciones_db: list[dict[str, Any]],
        db: Any,
    ) -> tuple[list[dict[str, Any]], bool, str | None]:
        """Devuelve recomendaciones y si se usó el camino degradado."""
        if not self.settings.sagemaker_endpoint_name:
            return self._desde_db(predicciones_db), False, None

        candidatas = predicciones_db[:3]
        if not candidatas:
            candidatas = [{"categoria": "general", "prediccion": 0.0}]

        resultados: list[dict[str, Any]] = []
        errores: list[str] = []

        for fila in candidatas:
            categoria = str(fila.get("categoria", "general"))
            try:
                features = await db.get_features_categoria(usuario_id, categoria)
            except Exception as exc:
                errores.append(f"db:{exc}")
                continue

            payload = {
                "num_vistas_categoria": int(features.get("num_vistas_categoria", 0)),
                "num_clics_categoria": int(features.get("num_clics_categoria", 0)),
                "num_compras_categoria": int(features.get("num_compras_categoria", 0)),
                "total_gastado_categoria": float(features.get("total_gastado_categoria", 0.0)),
                "dias_ultima_compra": int(features.get("dias_ultima_compra", 999)),
                "frecuencia_compra": int(perfil_raw.get("frecuencia_compra", 0)),
                "ticket_promedio": float(perfil_raw.get("ticket_promedio", 0.0)),
                "edad": int(perfil_raw.get("edad") or 30),
                "acepta_marketing": int(perfil_raw.get("acepta_marketing") or 0),
            }

            try:
                respuesta = await asyncio.wait_for(
                    asyncio.to_thread(self._invocar, payload),
                    timeout=self.settings.sagemaker_timeout_seconds,
                )
                normalizadas = _parsear_salida(respuesta, categoria)
                if not normalizadas:
                    errores.append(f"{categoria}: respuesta vacía")
                resultados.extend(normalizadas)
            except asyncio.TimeoutError:
                errores.append(f"{categoria}: timeout")
            except Exception as exc:
                errores.append(f"{categoria}: {type(exc).__name__}")

        if resultados:
            resultados.sort(key=lambda item: item.get("propension", 0.0), reverse=True)
            motivo = "; ".join(errores[:2]) if errores else None
            return resultados, False, motivo

        motivo = "; ".join(errores[:3]) or "SageMaker no devolvió resultados"
        logger.warning("SageMaker degradado, se usan predicciones de PostgreSQL: %s", motivo)
        return self._desde_db(predicciones_db), True, motivo

    def _invocar(self, payload: dict[str, Any]) -> Any:
        respuesta = self._runtime().invoke_endpoint(
            EndpointName=self.settings.sagemaker_endpoint_name,
            Body=json.dumps(payload).encode("utf-8"),
            ContentType="application/json",
            Accept="application/json",
        )
        cuerpo = respuesta["Body"].read()
        if isinstance(cuerpo, bytes):
            cuerpo = cuerpo.decode("utf-8")
        return json.loads(cuerpo)

    @staticmethod
    def _desde_db(predicciones_db: list[dict[str, Any]]) -> list[dict[str, Any]]:
        recomendaciones: list[dict[str, Any]] = []
        for fila in predicciones_db[:5]:
            probabilidad = float(fila.get("prediccion", 0.0) or 0.0)
            recomendaciones.append(
                {
                    "categoria": str(fila.get("categoria", "general")),
                    "propension": round(max(0.0, min(1.0, probabilidad)), 4),
                    "propension_etiqueta": str(
                        fila.get("propension") or _etiqueta(probabilidad)
                    ),
                    "origen": "predicciones_db",
                }
            )
        return recomendaciones
