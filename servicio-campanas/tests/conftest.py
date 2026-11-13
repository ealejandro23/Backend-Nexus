from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app.campaigns import CampaignService, S3Exporter
from app.config import Settings
from app.llm import LLMResult
from app.main import create_app
from app.queue import QueueUnavailable


class FakeDB:
    def __init__(self) -> None:
        self.usuarios: dict[str, dict[str, Any]] = {
            "U100000": {
                "usuario_id": "U100000",
                "edad": 34,
                "acepta_marketing": 1,
                "region": "Metropolitana",
                "comuna": "Providencia",
                "frecuencia_compra": 4,
                "ticket_promedio": 45000.0,
            }
        }
        self.predicciones: dict[str, list[dict[str, Any]]] = {
            "U100000": [
                {"categoria": "audio", "prediccion": 0.82, "propension": "alta"},
                {"categoria": "video", "prediccion": 0.55, "propension": "media"},
            ]
        }
        self.campanas: list[dict[str, Any]] = []
        self.ping_error = False

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def ensure_schema(self) -> None:
        return None

    async def ping(self) -> float:
        if self.ping_error:
            raise ConnectionError("postgres caído")
        return 1.5

    async def get_usuario(self, usuario_id: str) -> dict[str, Any] | None:
        return self.usuarios.get(usuario_id)

    async def get_predicciones(
        self, usuario_id: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        return self.predicciones.get(usuario_id, [])[:limit]

    async def get_features_categoria(
        self, usuario_id: str, categoria: str
    ) -> dict[str, Any]:
        return {
            "num_compras_categoria": 2,
            "total_gastado_categoria": 120000.0,
            "dias_ultima_compra": 15,
            "num_vistas_categoria": 10,
            "num_clics_categoria": 4,
        }

    async def guardar_campana(self, campana: dict[str, Any]) -> None:
        self.campanas.append(dict(campana))

    async def get_ultima_campana(self, usuario_id: str) -> dict[str, Any] | None:
        propias = [c for c in self.campanas if c["usuario_id"] == usuario_id]
        return propias[-1] if propias else None

    async def get_campana_por_job(self, job_id: str) -> dict[str, Any] | None:
        for campana in self.campanas:
            if campana["job_id"] == job_id:
                return campana
        return None


class FakeQueue:
    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []
        self.fail_publish = False
        self.handler = None
        self.health_result = ("ok", "0 mensajes en cola", 1.0)

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def publish(self, job: dict[str, Any], retry: int = 0) -> None:
        if self.fail_publish:
            raise QueueUnavailable("cola caída")
        self.published.append(job)

    async def consume(self, handler: Any) -> str:
        self.handler = handler
        return "tag-test"

    async def health(self) -> tuple[str, str, float]:
        return self.health_result


class FakeLLM:
    def __init__(
        self,
        degradado: bool = False,
        health: tuple[str, str, float] = ("ok", "API NVIDIA responde", 1.0),
    ) -> None:
        self.degradado = degradado
        self.health_result = health
        self.llamadas = 0

    async def generate(self, *args: Any, **kwargs: Any) -> LLMResult:
        self.llamadas += 1
        return LLMResult(
            asunto="Tu selección de audio",
            mensaje="Descubre los audífonos que combinan con tu historial.",
            degradado=self.degradado,
            intentos=1,
            latencia_ms=12.0,
            error="HTTP 429" if self.degradado else None,
            modelo="nvidia/nemotron-3.5-lightning-30b-a3b",
        )

    async def health(self) -> tuple[str, str, float]:
        return self.health_result

    async def close(self) -> None:
        return None


class FakeSageMaker:
    def __init__(self, health: tuple[str, str, float] = ("ok", "InService", 1.0)) -> None:
        self.health_result = health
        self.degradado = False

    async def health(self) -> tuple[str, str, float]:
        return self.health_result

    async def recomendar(self, *args: Any, **kwargs: Any) -> tuple[list[dict[str, Any]], bool, str | None]:
        recomendaciones = [
            {
                "categoria": "audio",
                "propension": 0.82,
                "propension_etiqueta": "alta",
                "origen": "sagemaker",
            },
            {
                "categoria": "video",
                "propension": 0.55,
                "propension_etiqueta": "media",
                "origen": "sagemaker",
            },
        ]
        return recomendaciones, self.degradado, "SageMaker timeout" if self.degradado else None


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        nvidia_api_key="test-key",
        llm_backoff_seconds=0,
        llm_max_retries=2,
        llm_timeout_seconds=1,
        llm_max_wait_seconds=2,
        s3_bucket="",
        anonymization_salt="test-salt",
    )


@pytest.fixture
def fakes() -> tuple[FakeDB, FakeQueue, FakeLLM, FakeSageMaker]:
    return FakeDB(), FakeQueue(), FakeLLM(), FakeSageMaker()


def construir_servicio(
    settings: Settings,
    db: FakeDB,
    queue: FakeQueue,
    llm: Any,
    sagemaker: Any,
) -> CampaignService:
    return CampaignService(settings, db, queue, llm, sagemaker, S3Exporter(settings))


@pytest_asyncio.fixture
async def cliente(
    settings: Settings, fakes: tuple[FakeDB, FakeQueue, FakeLLM, FakeSageMaker]
) -> Any:
    db, queue, llm, sagemaker = fakes
    app = create_app(settings=settings, db=db, queue=queue, llm=llm, sagemaker=sagemaker)
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, db, queue, llm, sagemaker
