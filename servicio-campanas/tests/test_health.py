"""Prueba propia: health con el estado de cada dependencia por separado.

Verifica que GET /api/health no oculte fallas: base de datos, SageMaker,
RabbitMQ y LLM se reportan de forma independiente y el estado global cambia
según la criticidad.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_health_reporta_cada_dependencia(cliente) -> None:
    client, db, queue, llm, sagemaker = cliente

    respuesta = await client.get("/api/health")

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert set(datos["checks"]) == {"base_datos", "sagemaker", "cola", "llm"}
    assert datos["checks"]["base_datos"]["estado"] == "ok"
    assert datos["checks"]["cola"]["estado"] == "ok"
    assert datos["checks"]["llm"]["estado"] == "ok"
    assert datos["checks"]["sagemaker"]["estado"] == "ok"
    assert datos["estado"] == "ok"
    assert all("latencia_ms" in check for check in datos["checks"].values())


async def test_health_degrada_si_llm_falla(cliente) -> None:
    client, db, queue, llm, sagemaker = cliente
    llm.health_result = ("error", "timeout contra NVIDIA", 5000.0)

    respuesta = await client.get("/api/health")
    datos = respuesta.json()

    assert respuesta.status_code == 200
    assert datos["checks"]["llm"]["estado"] == "error"
    assert datos["estado"] == "degradado"


async def test_health_degrada_si_sagemaker_no_configurado(cliente) -> None:
    client, db, queue, llm, sagemaker = cliente
    sagemaker.health_result = ("no_configurado", "sin endpoint", 0.0)

    respuesta = await client.get("/api/health")
    datos = respuesta.json()

    assert datos["checks"]["sagemaker"]["estado"] == "no_configurado"
    assert datos["estado"] == "ok"


async def test_health_es_error_si_base_de_datos_cae(cliente) -> None:
    client, db, queue, llm, sagemaker = cliente
    db.ping_error = True

    respuesta = await client.get("/api/health")
    datos = respuesta.json()

    assert respuesta.status_code == 200
    assert datos["checks"]["base_datos"]["estado"] == "error"
    assert datos["estado"] == "error"


async def test_liveness_no_depende_de_servicios_externos(cliente) -> None:
    client, db, queue, llm, sagemaker = cliente
    db.ping_error = True
    llm.health_result = ("error", "caído", 1.0)
    queue.health_result = ("error", "caída", 1.0)

    respuesta = await client.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "ok"
