"""Entrypoint del contenedor worker.

Consume jobs de RabbitMQ y ejecuta el pipeline de campaña. Se ejecuta como
`python -m app.worker_main` y comparte la misma imagen que la API.
"""

from __future__ import annotations

import asyncio
import logging
import signal

from .campaigns import CampaignService, S3Exporter
from .config import get_settings
from .database import Database
from .llm import NvidiaLLMClient
from .queue import RabbitQueue
from .sagemaker import SageMakerRecommender

logger = logging.getLogger(__name__)


async def ejecutar_worker() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    db = Database(settings)
    queue = RabbitQueue(settings)
    llm = NvidiaLLMClient(settings)
    sagemaker = SageMakerRecommender(settings)
    service = CampaignService(
        settings, db, queue, llm, sagemaker, S3Exporter(settings)
    )

    await db.connect()
    await db.ensure_schema()
    await queue.esperar_conexion()
    await queue.consume(service.procesar_job)
    logger.info("Worker de campañas listo")

    detener = asyncio.Event()

    def _solicitar_parada(*_: object) -> None:
        detener.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _solicitar_parada)
        except (NotImplementedError, RuntimeError):
            try:
                signal.signal(sig, _solicitar_parada)
            except (ValueError, OSError):
                pass

    try:
        await detener.wait()
    finally:
        logger.info("Cerrando worker de campañas")
        await queue.close()
        await llm.close()
        await db.close()


def main() -> None:
    asyncio.run(ejecutar_worker())


if __name__ == "__main__":
    main()
