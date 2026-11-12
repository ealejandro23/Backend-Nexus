"""Orquestación de una campaña: perfil -> anonimización -> modelo -> LLM."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .anonymizer import anonimizar_perfil, hash_usuario
from .config import Settings
from .database import Database
from .llm import NvidiaLLMClient
from .queue import RabbitQueue, QueueUnavailable
from .sagemaker import SageMakerRecommender
from .schemas import CampaignRequest

logger = logging.getLogger(__name__)


class UserNotFound(LookupError):
    pass


class CampaignNotFound(LookupError):
    pass


class S3Exporter:
    """Exporta la campaña a S3 para auditoría y consumo desde Mailchimp."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Any = None

    def _s3(self) -> Any:
        if self._client is None:
            import boto3

            self._client = boto3.client("s3", region_name=self.settings.aws_region)
        return self._client

    async def exportar(self, campana: dict[str, Any]) -> None:
        if not self.settings.s3_export_enabled or not self.settings.s3_bucket:
            return
        usuario_hash = hash_usuario(
            str(campana.get("usuario_id", "")), self.settings.anonymization_salt
        )
        key = (
            f"{self.settings.s3_prefix}/{usuario_hash}/"
            f"{campana.get('job_id', uuid4())}.json"
        )
        cuerpo = json.dumps(campana, ensure_ascii=False, default=str).encode("utf-8")
        try:
            await asyncio.to_thread(
                self._s3().put_object,
                Bucket=self.settings.s3_bucket,
                Key=key,
                Body=cuerpo,
                ContentType="application/json",
                ServerSideEncryption="AES256",
            )
            logger.info("Campaña exportada a s3://%s/%s", self.settings.s3_bucket, key)
        except Exception as exc:
            # La exportación es secundaria: no debe tumbar la campaña.
            logger.warning("No se pudo exportar la campaña a S3: %s", exc)


class CampaignService:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        queue: RabbitQueue,
        llm: NvidiaLLMClient,
        sagemaker: SageMakerRecommender,
        exporter: S3Exporter | None = None,
    ) -> None:
        self.settings = settings
        self.db = db
        self.queue = queue
        self.llm = llm
        self.sagemaker = sagemaker
        self.exporter = exporter or S3Exporter(settings)

    async def crear_job(
        self, usuario_id: str, request: CampaignRequest
    ) -> tuple[str, dict[str, Any] | None]:
        perfil = await self.db.get_usuario(usuario_id)
        if perfil is None:
            raise UserNotFound(usuario_id)

        job = {
            "job_id": str(uuid4()),
            "usuario_id": usuario_id,
            "canal": request.canal,
            "tono": request.tono,
            "incluir_descuento": request.incluir_descuento,
            "creado_en": datetime.now(timezone.utc).isoformat(),
        }

        try:
            await self.queue.publish(job)
            return "en_cola", job
        except QueueUnavailable as exc:
            if not self.settings.queue_inline_fallback:
                raise
            logger.warning(
                "Cola no disponible (%s). Procesando la campaña en línea.", exc
            )
            campana = await self.procesar_job(job)
            return "procesado_en_linea", campana

    async def procesar_job(self, job: dict[str, Any]) -> dict[str, Any]:
        usuario_id = str(job["usuario_id"])
        perfil = await self.db.get_usuario(usuario_id)
        if perfil is None:
            raise UserNotFound(usuario_id)

        predicciones = await self.db.get_predicciones(usuario_id, limit=5)
        perfil_anonimizado = anonimizar_perfil(perfil, self.settings.anonymization_salt)
        perfil_anonimizado["canal_preferido"] = job.get("canal", "email")

        recomendaciones, sm_degradado, motivo_sm = await self.sagemaker.recomendar(
            usuario_id, perfil, predicciones, self.db
        )
        perfil_anonimizado["categorias"] = [
            rec["categoria"] for rec in recomendaciones[:5] if rec.get("categoria")
        ]
        if predicciones:
            perfil_anonimizado["compras_previas"] = len(predicciones)

        resultado = await self.llm.generate(
            perfil_anonimizado,
            recomendaciones,
            canal=str(job.get("canal", "email")),
            tono=str(job.get("tono", "cercano")),
            incluir_descuento=bool(job.get("incluir_descuento", False)),
        )

        motivos = [motivo for motivo in (motivo_sm, resultado.error) if motivo]
        campana = {
            "job_id": str(job["job_id"]),
            "usuario_id": usuario_id,
            "canal": str(job.get("canal", "email")),
            "asunto": resultado.asunto,
            "mensaje": resultado.mensaje,
            "recomendaciones": recomendaciones,
            "degradado": bool(resultado.degradado or sm_degradado),
            "motivo_degradado": "; ".join(motivos)[:300] or None,
            "modelo_llm": resultado.modelo or self.settings.nvidia_model,
            "creado_en": datetime.now(timezone.utc),
        }

        await self.db.guardar_campana(campana)
        await self.exporter.exportar(campana)
        logger.info(
            "Campaña %s generada para %s degradado=%s intentos=%s",
            campana["job_id"],
            hash_usuario(usuario_id, self.settings.anonymization_salt),
            campana["degradado"],
            resultado.intentos,
        )
        return campana

    async def get_ultima(self, usuario_id: str) -> dict[str, Any]:
        campana = await self.db.get_ultima_campana(usuario_id)
        if campana is None:
            raise CampaignNotFound(usuario_id)
        return campana

    async def get_job(self, job_id: str) -> dict[str, Any]:
        campana = await self.db.get_campana_por_job(job_id)
        if campana is None:
            raise CampaignNotFound(job_id)
        return campana
