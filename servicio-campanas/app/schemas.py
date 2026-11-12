"""Modelos de entrada/salida de la API de campañas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CampaignRequest(BaseModel):
    canal: Literal["email", "push", "sms", "whatsapp"] = "email"
    tono: Literal["cercano", "formal", "entusiasta", "conciso"] = "cercano"
    incluir_descuento: bool = False


class CampaignJob(BaseModel):
    job_id: str
    usuario_id: str
    canal: str = "email"
    tono: str = "cercano"
    incluir_descuento: bool = False
    creado_en: datetime = Field(default_factory=datetime.utcnow)


class CampaignAccepted(BaseModel):
    job_id: str
    usuario_id: str
    estado: Literal["en_cola", "procesado_en_linea"]
    mensaje: str


class Recommendation(BaseModel):
    categoria: str
    propension: float = 0.0
    propension_etiqueta: str = "media"
    origen: str = "predicciones_db"


class CampaignResult(BaseModel):
    job_id: str
    usuario_id: str
    canal: str
    asunto: str
    mensaje: str
    recomendaciones: list[Recommendation] = Field(default_factory=list)
    degradado: bool = False
    motivo_degradado: str | None = None
    modelo_llm: str
    creado_en: datetime = Field(default_factory=datetime.utcnow)


class CheckResult(BaseModel):
    estado: Literal["ok", "degradado", "error", "no_configurado"]
    detalle: str = ""
    latencia_ms: float = 0.0


class HealthResponse(BaseModel):
    estado: Literal["ok", "degradado", "error"]
    checks: dict[str, CheckResult]
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
