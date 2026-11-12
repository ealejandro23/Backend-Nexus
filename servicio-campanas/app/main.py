"""API HTTP del servicio de campañas (EP3).

Rutas:
  POST /api/campanas/{usuario}  -> encola una campaña personalizada
  GET  /api/campanas/{usuario}  -> última campaña generada
  GET  /api/campanas/jobs/{id}  -> estado de un job
  GET  /api/health              -> health de DB, SageMaker, cola y LLM
  GET  /health                  -> liveness para Docker
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .campaigns import (
    CampaignNotFound,
    CampaignService,
    S3Exporter,
    UserNotFound,
)
from .config import Settings, get_settings
from .database import Database
from .health import construir_health
from .llm import NvidiaLLMClient
from .queue import QueueUnavailable, RabbitQueue
from .sagemaker import SageMakerRecommender
from .schemas import (
    CampaignAccepted,
    CampaignRequest,
    CampaignResult,
    HealthResponse,
)

logger = logging.getLogger(__name__)


def _configurar_logging(nivel: str) -> None:
    logging.basicConfig(
        level=getattr(logging, nivel.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def create_app(
    settings: Settings | None = None,
    db: Any | None = None,
    queue: Any | None = None,
    llm: Any | None = None,
    sagemaker: Any | None = None,
    service: Any | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    _configurar_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.db = db or Database(settings)
        app.state.queue = queue or RabbitQueue(settings)
        app.state.llm = llm or NvidiaLLMClient(settings)
        app.state.sagemaker = sagemaker or SageMakerRecommender(settings)
        app.state.service = service or CampaignService(
            settings,
            app.state.db,
            app.state.queue,
            app.state.llm,
            app.state.sagemaker,
            S3Exporter(settings),
        )

        # La API debe partir aunque las dependencias externas estén caídas.
        try:
            await app.state.db.connect()
            await app.state.db.ensure_schema()
        except Exception as exc:
            logger.error("Base de datos no disponible al arrancar: %s", exc)
        try:
            await app.state.queue.connect()
        except Exception as exc:
            logger.warning("RabbitMQ no disponible al arrancar: %s", exc)

        logger.info("%s %s iniciado", settings.app_name, settings.app_version)
        try:
            yield
        finally:
            cierre = getattr(app.state.llm, "close", None)
            if cierre is not None:
                try:
                    await cierre()
                except Exception:
                    pass
            try:
                await app.state.queue.close()
            except Exception:
                pass
            try:
                await app.state.db.close()
            except Exception:
                pass

    app = FastAPI(
        title="Nexo Campañas EP3",
        description=(
            "Worker de campañas personalizadas: RabbitMQ + SageMaker + LLM NVIDIA, "
            "con anonimización, timeout, reintentos y modo degradado."
        ),
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(UserNotFound)
    async def _usuario_no_encontrado(_: Request, exc: UserNotFound) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": f"Usuario no encontrado: {exc}"},
        )

    @app.exception_handler(CampaignNotFound)
    async def _campana_no_encontrada(_: Request, exc: CampaignNotFound) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": f"Campaña no encontrada: {exc}"},
        )

    @app.exception_handler(QueueUnavailable)
    async def _cola_no_disponible(_: Request, exc: QueueUnavailable) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": f"Cola no disponible: {exc}"},
        )

    @app.get("/health", tags=["operación"])
    async def liveness(request: Request) -> dict[str, str]:
        return {"status": "ok", "version": request.app.state.settings.app_version}

    @app.get("/api/health", response_model=HealthResponse, tags=["operación"])
    async def health(request: Request) -> HealthResponse:
        state = request.app.state
        return await construir_health(
            state.settings,
            state.db,
            state.queue,
            state.llm,
            state.sagemaker,
        )

    @app.post(
        "/api/campanas/{usuario}",
        response_model=CampaignAccepted,
        status_code=202,
        tags=["campañas"],
    )
    async def crear_campana(
        usuario: str, request: Request, body: CampaignRequest | None = None
    ) -> CampaignAccepted:
        estado, campana = await request.app.state.service.crear_job(
            usuario, body or CampaignRequest()
        )
        if estado == "procesado_en_linea":
            mensaje = "Campaña generada en línea porque la cola no estaba disponible."
        else:
            mensaje = "Campaña encolada. Consulta GET /api/campanas/{usuario} en unos segundos."
        return CampaignAccepted(
            job_id=campana["job_id"] if campana else "",
            usuario_id=usuario,
            estado=estado,
            mensaje=mensaje,
        )

    @app.get(
        "/api/campanas/{usuario}",
        response_model=CampaignResult,
        tags=["campañas"],
    )
    async def ultima_campana(usuario: str, request: Request) -> CampaignResult:
        campana = await request.app.state.service.get_ultima(usuario)
        return CampaignResult(**campana)

    @app.get(
        "/api/campanas/jobs/{job_id}",
        response_model=CampaignResult,
        tags=["campañas"],
    )
    async def campana_por_job(job_id: str, request: Request) -> CampaignResult:
        campana = await request.app.state.service.get_job(job_id)
        return CampaignResult(**campana)

    return app


app = create_app()
