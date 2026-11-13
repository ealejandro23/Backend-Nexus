"""Cliente del LLM de NVIDIA con timeout, reintentos y modo degradado.

El worker nunca debe romperse porque el proveedor del LLM esté lento o
limitando peticiones. Si se agotan los reintentos (por ejemplo, ante 429),
se devuelve una campaña de respaldo construida sólo con datos anonimizados.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from .config import Settings
from .prompts import construir_prompt

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


@dataclass
class LLMResult:
    asunto: str
    mensaje: str
    degradado: bool
    intentos: int
    latencia_ms: float
    error: str | None = None
    modelo: str = ""
    respuesta_cruda: dict[str, Any] = field(default_factory=dict)


def _limpiar_fences(texto: str) -> str:
    limpio = texto.strip()
    if limpio.startswith("```"):
        lineas = limpio.splitlines()
        if lineas and lineas[0].startswith("```"):
            lineas = lineas[1:]
        if lineas and lineas[-1].strip().startswith("```"):
            lineas = lineas[:-1]
        limpio = "\n".join(lineas).strip()
    return limpio


def _parsear_contenido(contenido: str) -> tuple[str, str]:
    """Intenta leer el JSON pedido; si falla, usa el texto como mensaje."""
    limpio = _limpiar_fences(contenido)
    try:
        data = json.loads(limpio)
        if isinstance(data, dict):
            asunto = str(data.get("asunto", "")).strip()
            mensaje = str(data.get("mensaje", "")).strip()
            if mensaje:
                return asunto or "Recomendaciones pensadas para ti", mensaje
    except json.JSONDecodeError:
        pass

    mensaje = limpio
    if not mensaje:
        mensaje = "Tenemos recomendaciones pensadas para ti."
    primera_linea = mensaje.splitlines()[0].strip()
    asunto = primera_linea[:70] if primera_linea else "Recomendaciones para ti"
    return asunto, mensaje


def _fallback(
    perfil_anonimizado: dict[str, Any],
    recomendaciones: list[dict[str, Any]],
    canal: str,
    motivo: str,
) -> tuple[str, str]:
    """Campaña de respaldo determinista, sin PII y sin llamar al LLM."""
    categorias: list[str] = []
    for rec in recomendaciones:
        categoria = str(rec.get("categoria", "")).strip()
        if categoria and categoria not in categorias:
            categorias.append(categoria)

    if categorias:
        listado = ", ".join(categorias[:3])
        asunto = f"Una selección de {listado} para ti"
        mensaje = (
            f"Preparamos una selección especial de {listado} pensando en lo que "
            f"has explorado en Nexo. Revisa las novedades y encuentra tu próxima "
            f"compra favorita. Este mensaje se generó automáticamente porque el "
            f"servicio de redacción no estaba disponible."
        )
    else:
        asunto = "Descubre lo nuevo en Nexo"
        mensaje = (
            "Tenemos novedades que podrían interesarte. Visita Nexo y descubre "
            "las categorías disponibles. Este mensaje se generó automáticamente "
            "porque el servicio de redacción no estaba disponible."
        )

    # El canal se usa sólo para dejar trazabilidad en el asunto del fallback.
    if canal == "push":
        asunto = asunto[:60]
    return asunto, mensaje


class NvidiaLLMClient:
    """Cliente asíncrono para la API OpenAI-compatible de NVIDIA."""

    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.settings.llm_timeout_seconds),
                transport=self._transport,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.nvidia_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def generate(
        self,
        perfil_anonimizado: dict[str, Any],
        recomendaciones: list[dict[str, Any]],
        canal: str = "email",
        tono: str = "cercano",
        incluir_descuento: bool = False,
    ) -> LLMResult:
        inicio = time.monotonic()
        system_prompt, user_prompt = construir_prompt(
            perfil_anonimizado,
            recomendaciones,
            canal=canal,
            tono=tono,
            incluir_descuento=incluir_descuento,
        )

        if not self.settings.nvidia_api_key:
            asunto, mensaje = _fallback(
                perfil_anonimizado, recomendaciones, canal, "NVIDIA_API_KEY no configurada"
            )
            return LLMResult(
                asunto=asunto,
                mensaje=mensaje,
                degradado=True,
                intentos=0,
                latencia_ms=(time.monotonic() - inicio) * 1000,
                error="NVIDIA_API_KEY no configurada",
                modelo=self.settings.nvidia_model,
            )

        payload = {
            "model": self.settings.nvidia_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.settings.llm_temperature,
            "max_tokens": self.settings.llm_max_tokens,
            "stream": False,
        }
        if self.settings.llm_disable_thinking:
            # Los modelos Nemotron 3 devuelven la respuesta final en "content"
            # sólo si se desactiva el razonamiento; si no, "content" es null.
            payload["chat_template_kwargs"] = {"enable_thinking": False}

        deadline = inicio + self.settings.llm_max_wait_seconds
        ultimo_error = "sin intentos"
        intentos = 0
        client = self._get_client()

        while intentos <= self.settings.llm_max_retries:
            intentos += 1
            restante = deadline - time.monotonic()
            if restante <= 0:
                ultimo_error = "tiempo máximo de espera agotado"
                break

            try:
                response = await client.post(
                    self.settings.nvidia_chat_url,
                    headers=self._headers(),
                    json=payload,
                    timeout=min(self.settings.llm_timeout_seconds, restante),
                )
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                ultimo_error = f"{type(exc).__name__}: {exc}"
                logger.warning("LLM intento %s falló: %s", intentos, ultimo_error)
                if intentos <= self.settings.llm_max_retries and await self._esperar(
                    intentos, deadline, None
                ):
                    continue
                break

            if response.status_code in RETRYABLE_STATUS:
                ultimo_error = f"HTTP {response.status_code}"
                logger.warning("LLM intento %s recibió %s", intentos, ultimo_error)
                if intentos <= self.settings.llm_max_retries and await self._esperar(
                    intentos, deadline, response.headers.get("Retry-After")
                ):
                    continue
                break

            if response.status_code >= 400:
                ultimo_error = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.error("LLM error no reintentable: %s", ultimo_error)
                break

            try:
                data = response.json()
                contenido = data["choices"][0]["message"].get("content")
                if not contenido or not str(contenido).strip():
                    raise ValueError(
                        "respuesta sin contenido final (razonamiento agotado)"
                    )
                asunto, mensaje = _parsear_contenido(str(contenido))
                return LLMResult(
                    asunto=asunto,
                    mensaje=mensaje,
                    degradado=False,
                    intentos=intentos,
                    latencia_ms=(time.monotonic() - inicio) * 1000,
                    modelo=self.settings.nvidia_model,
                    respuesta_cruda={"usage": data.get("usage", {})},
                )
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                ultimo_error = f"respuesta inválida: {exc}"
                logger.warning("LLM devolvió una respuesta inválida: %s", ultimo_error)
                break

        asunto, mensaje = _fallback(perfil_anonimizado, recomendaciones, canal, ultimo_error)
        return LLMResult(
            asunto=asunto,
            mensaje=mensaje,
            degradado=True,
            intentos=intentos,
            latencia_ms=(time.monotonic() - inicio) * 1000,
            error=ultimo_error,
            modelo=self.settings.nvidia_model,
        )

    async def _esperar(
        self, intento: int, deadline: float, retry_after: str | None
    ) -> bool:
        """Espera con backoff exponencial respetando Retry-After."""
        espera = self.settings.llm_backoff_seconds * (2 ** (intento - 1))
        if retry_after:
            try:
                espera = max(espera, float(retry_after))
            except ValueError:
                pass
        restante = deadline - time.monotonic()
        if restante <= 0:
            return False
        espera = min(espera, max(0.0, restante))
        if espera > 0:
            await asyncio.sleep(espera)
        return True

    async def health(self) -> tuple[str, str, float]:
        """Verifica disponibilidad del LLM sin gastar tokens de generación."""
        inicio = time.monotonic()
        if not self.settings.nvidia_api_key:
            return "no_configurado", "NVIDIA_API_KEY no configurada", 0.0
        try:
            response = await self._get_client().get(
                self.settings.nvidia_models_url,
                headers=self._headers(),
                timeout=self.settings.llm_health_timeout_seconds,
            )
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            return "error", f"{type(exc).__name__}: {exc}", (time.monotonic() - inicio) * 1000

        latencia = (time.monotonic() - inicio) * 1000
        if response.status_code == 200:
            try:
                modelos = {
                    str(item.get("id"))
                    for item in response.json().get("data", [])
                    if isinstance(item, dict)
                }
            except ValueError:
                modelos = set()
            if modelos and self.settings.nvidia_model not in modelos:
                return (
                    "degradado",
                    f"modelo {self.settings.nvidia_model} no disponible",
                    latencia,
                )
            return "ok", "API de NVIDIA responde", latencia
        if response.status_code == 429:
            return "degradado", "API de NVIDIA limitando peticiones (429)", latencia
        return "error", f"HTTP {response.status_code}", latencia
