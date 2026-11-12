"""Health check que reporta cada dependencia por separado.

GET /api/health responde siempre con el detalle de:
  - base_datos
  - sagemaker
  - cola (RabbitMQ)
  - llm (NVIDIA)

El estado global es "error" sólo si la base de datos no responde, porque sin
ella no se puede construir ninguna campaña. El resto de fallas se reportan
como "degradado" y el sistema sigue operando con sus respaldos.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable

from .config import Settings
from .schemas import CheckResult, HealthResponse

logger = logging.getLogger(__name__)

CheckFn = Callable[[], Awaitable[tuple[str, str, float]]]


async def _check(
    nombre: str, funcion: CheckFn, timeout: float
) -> CheckResult:
    inicio = time.monotonic()
    try:
        estado, detalle, latencia = await asyncio.wait_for(funcion(), timeout=timeout)
        return CheckResult(
            estado=estado,  # type: ignore[arg-type]
            detalle=detalle,
            latencia_ms=round(latencia or (time.monotonic() - inicio) * 1000, 2),
        )
    except asyncio.TimeoutError:
        return CheckResult(
            estado="error",
            detalle=f"timeout después de {timeout}s",
            latencia_ms=round((time.monotonic() - inicio) * 1000, 2),
        )
    except Exception as exc:
        logger.warning("Health %s falló: %s", nombre, exc)
        return CheckResult(
            estado="error",
            detalle=f"{type(exc).__name__}: {exc}",
            latencia_ms=round((time.monotonic() - inicio) * 1000, 2),
        )


async def construir_health(
    settings: Settings,
    db: object,
    queue: object,
    llm: object,
    sagemaker: object,
) -> HealthResponse:
    timeout = settings.health_timeout_seconds

    async def check_db() -> tuple[str, str, float]:
        latencia = await db.ping()  # type: ignore[attr-defined]
        return "ok", "PostgreSQL responde", latencia

    checks = await asyncio.gather(
        _check("base_datos", check_db, timeout),
        _check("sagemaker", sagemaker.health, timeout),  # type: ignore[attr-defined]
        _check("cola", queue.health, timeout),  # type: ignore[attr-defined]
        _check("llm", llm.health, timeout),  # type: ignore[attr-defined]
    )

    resultado = {
        "base_datos": checks[0],
        "sagemaker": checks[1],
        "cola": checks[2],
        "llm": checks[3],
    }

    if resultado["base_datos"].estado == "error":
        estado_global = "error"
    elif any(
        check.estado in ("error", "degradado")
        for check in resultado.values()
        if check.estado != "no_configurado"
    ):
        estado_global = "degradado"
    else:
        estado_global = "ok"

    return HealthResponse(
        estado=estado_global,  # type: ignore[arg-type]
        checks=resultado,
        version=settings.app_version,
    )
