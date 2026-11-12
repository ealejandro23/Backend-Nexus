"""Prueba 6: el worker sobrevive a un LLM caído o limitando peticiones (429).

Se valida el cliente NVIDIA y el pipeline completo de campaña. En ambos casos
debe generarse una campaña de respaldo, marcada como degradada, sin lanzar
excepciones y sin filtrar datos personales.
"""

from __future__ import annotations

import httpx
import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app.campaigns import CampaignService, S3Exporter
from app.config import Settings
from app.llm import NvidiaLLMClient
from app.main import create_app

from conftest import FakeDB, FakeQueue, FakeSageMaker


PERFIL = {
    "usuario_hash": "u_abc123",
    "rango_edad": "25-34",
    "acepta_marketing": 1,
    "categorias": ["audio"],
}
RECOMENDACIONES = [
    {"categoria": "audio", "propension": 0.82, "propension_etiqueta": "alta"}
]


def _cliente_con_transporte(settings: Settings, handler) -> NvidiaLLMClient:
    return NvidiaLLMClient(settings, transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_llm_429_reintenta_y_usa_modo_degradado(settings: Settings) -> None:
    llamadas = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        llamadas["n"] += 1
        return httpx.Response(429, headers={"Retry-After": "0"}, json={"error": "rate"})

    cliente = _cliente_con_transporte(settings, handler)
    resultado = await cliente.generate(PERFIL, RECOMENDACIONES, canal="email")
    await cliente.close()

    assert resultado.degradado is True
    assert resultado.intentos == settings.llm_max_retries + 1
    assert llamadas["n"] == settings.llm_max_retries + 1
    assert "429" in (resultado.error or "")
    assert "audio" in resultado.mensaje
    assert "@" not in resultado.mensaje


@pytest.mark.asyncio
async def test_llm_timeout_usa_modo_degradado(settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout simulado", request=request)

    cliente = _cliente_con_transporte(settings, handler)
    resultado = await cliente.generate(PERFIL, RECOMENDACIONES)
    await cliente.close()

    assert resultado.degradado is True
    assert resultado.intentos == settings.llm_max_retries + 1
    assert "ReadTimeout" in (resultado.error or "")
    assert resultado.mensaje


@pytest.mark.asyncio
async def test_llm_error_no_reintentable_no_agota_espera(settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    cliente = _cliente_con_transporte(settings, handler)
    resultado = await cliente.generate(PERFIL, RECOMENDACIONES)
    await cliente.close()

    assert resultado.degradado is True
    assert resultado.intentos == 1
    assert "401" in (resultado.error or "")


@pytest.mark.asyncio
async def test_pipeline_completo_con_llm_caido(settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "0"}, json={"error": "rate"})

    db = FakeDB()
    queue = FakeQueue()
    sagemaker = FakeSageMaker()
    llm = _cliente_con_transporte(settings, handler)
    servicio = CampaignService(settings, db, queue, llm, sagemaker, S3Exporter(settings))

    campana = await servicio.procesar_job(
        {
            "job_id": "11111111-1111-1111-1111-111111111111",
            "usuario_id": "U100000",
            "canal": "email",
            "tono": "cercano",
            "incluir_descuento": False,
        }
    )
    await llm.close()

    assert campana["degradado"] is True
    assert "429" in (campana["motivo_degradado"] or "")
    assert campana["asunto"]
    assert "audio" in campana["mensaje"]
    assert len(db.campanas) == 1
    # El worker no se cae y deja la campaña guardada para consulta.
    assert db.campanas[0]["job_id"] == campana["job_id"]


@pytest.mark.asyncio
async def test_health_reporta_llm_caido_sin_tumbar_el_servicio(
    settings: Settings,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "0"}, json={"error": "rate"})

    llm = _cliente_con_transporte(settings, handler)
    app = create_app(
        settings=settings,
        db=FakeDB(),
        queue=FakeQueue(),
        llm=llm,
        sagemaker=FakeSageMaker(),
    )
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            respuesta = await client.get("/api/health")
    await llm.close()

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert set(datos["checks"]) == {"base_datos", "sagemaker", "cola", "llm"}
    assert datos["checks"]["llm"]["estado"] == "degradado"
    assert datos["estado"] == "degradado"
