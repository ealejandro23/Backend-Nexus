"""Pruebas de la API de campañas y del fallback cuando la cola no responde."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_post_campana_encola_job(cliente) -> None:
    client, db, queue, llm, sagemaker = cliente

    respuesta = await client.post(
        "/api/campanas/U100000",
        json={"canal": "email", "tono": "cercano"},
    )

    assert respuesta.status_code == 202
    datos = respuesta.json()
    assert datos["estado"] == "en_cola"
    assert datos["usuario_id"] == "U100000"
    assert len(queue.published) == 1
    assert queue.published[0]["usuario_id"] == "U100000"
    assert datos["job_id"] == queue.published[0]["job_id"]


async def test_post_usuario_inexistente_404(cliente) -> None:
    client, *_ = cliente

    respuesta = await client.post("/api/campanas/NO-EXISTE")

    assert respuesta.status_code == 404
    assert "no encontrado" in respuesta.json()["detail"].lower()


async def test_post_sin_cola_procesa_en_linea(cliente) -> None:
    client, db, queue, llm, sagemaker = cliente
    queue.fail_publish = True

    respuesta = await client.post("/api/campanas/U100000")

    assert respuesta.status_code == 202
    assert respuesta.json()["estado"] == "procesado_en_linea"
    assert len(db.campanas) == 1
    assert db.campanas[0]["degradado"] is False


async def test_get_ultima_campana(cliente) -> None:
    client, db, queue, llm, sagemaker = cliente
    queue.fail_publish = True
    await client.post("/api/campanas/U100000")

    respuesta = await client.get("/api/campanas/U100000")

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["usuario_id"] == "U100000"
    assert datos["asunto"]
    assert datos["recomendaciones"][0]["categoria"] == "audio"


async def test_get_campana_por_job(cliente) -> None:
    client, db, queue, llm, sagemaker = cliente
    queue.fail_publish = True
    creacion = await client.post("/api/campanas/U100000")
    job_id = creacion.json()["job_id"]

    respuesta = await client.get(f"/api/campanas/jobs/{job_id}")

    assert respuesta.status_code == 200
    assert respuesta.json()["job_id"] == job_id


async def test_get_campana_inexistente_404(cliente) -> None:
    client, *_ = cliente

    respuesta = await client.get("/api/campanas/U100000")

    assert respuesta.status_code == 404
