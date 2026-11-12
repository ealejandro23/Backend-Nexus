"""Cola RabbitMQ: publicación de jobs y consumo por parte del worker."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message

from .config import Settings

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], Awaitable[Any]]


class QueueUnavailable(RuntimeError):
    pass


class RabbitQueue:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._queue: aio_pika.abc.AbstractQueue | None = None
        self._handler: Handler | None = None

    async def connect(self) -> None:
        try:
            self._connection = await aio_pika.connect_robust(
                self.settings.rabbitmq_dsn,
                timeout=self.settings.rabbitmq_connect_timeout,
            )
            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=self.settings.rabbitmq_prefetch)
            await self._declarar()
            logger.info(
                "Conectado a RabbitMQ cola=%s", self.settings.rabbitmq_queue
            )
        except Exception as exc:
            self._connection = None
            self._channel = None
            self._queue = None
            raise QueueUnavailable(f"RabbitMQ no disponible: {exc}") from exc

    async def _declarar(self) -> None:
        if self._channel is None:
            raise QueueUnavailable("Canal RabbitMQ no inicializado")
        exchange = await self._channel.declare_exchange(
            self.settings.rabbitmq_exchange, ExchangeType.DIRECT, durable=True
        )
        dlq = await self._channel.declare_queue(
            self.settings.rabbitmq_dlq, durable=True
        )
        await dlq.bind(exchange, routing_key=self.settings.rabbitmq_queue)
        self._queue = await self._channel.declare_queue(
            self.settings.rabbitmq_queue,
            durable=True,
            arguments={
                "x-dead-letter-exchange": self.settings.rabbitmq_exchange,
                "x-dead-letter-routing-key": self.settings.rabbitmq_queue,
            },
        )

    async def _canal(self) -> aio_pika.abc.AbstractChannel:
        if self._connection is None or self._connection.is_closed:
            await self.connect()
        if self._channel is None or self._channel.is_closed:
            assert self._connection is not None
            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=self.settings.rabbitmq_prefetch)
            await self._declarar()
        return self._channel

    async def publish(self, job: dict[str, Any], retry: int = 0) -> None:
        canal = await self._canal()
        mensaje = Message(
            body=json.dumps(job, ensure_ascii=False, default=str).encode("utf-8"),
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
            message_id=str(job.get("job_id", "")),
            headers={"x-retry": retry},
        )
        try:
            await canal.default_exchange.publish(
                mensaje, routing_key=self.settings.rabbitmq_queue
            )
        except Exception as exc:
            raise QueueUnavailable(f"No se pudo publicar en RabbitMQ: {exc}") from exc

    async def consume(self, handler: Handler) -> str:
        """Registra el handler. El proceso queda escuchando hasta que se cierre."""
        self._handler = handler
        canal = await self._canal()
        if self._queue is None or self._queue.channel.is_closed:
            await self._declarar()
        assert self._queue is not None
        tag = await self._queue.consume(self._on_message)
        logger.info("Worker escuchando cola %s", self.settings.rabbitmq_queue)
        return tag

    async def _on_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        try:
            job = json.loads(message.body.decode("utf-8"))
        except Exception as exc:
            logger.error("Mensaje inválido en la cola: %s", exc)
            await message.reject(requeue=False)
            return

        try:
            if self._handler is None:
                raise RuntimeError("No hay handler registrado")
            await self._handler(job)
            await message.ack()
        except Exception as exc:
            retry = int((message.headers or {}).get("x-retry", 0) or 0)
            if retry < self.settings.rabbitmq_max_retries:
                logger.warning(
                    "Job %s falló (intento %s/%s): %s. Reencolando.",
                    job.get("job_id"),
                    retry + 1,
                    self.settings.rabbitmq_max_retries,
                    exc,
                )
                try:
                    await self.publish(job, retry=retry + 1)
                    await message.ack()
                except Exception as publish_exc:
                    logger.error("No se pudo reencolar: %s", publish_exc)
                    await message.reject(requeue=True)
            else:
                logger.error(
                    "Job %s agotó reintentos, va a DLQ: %s", job.get("job_id"), exc
                )
                await message.reject(requeue=False)

    async def health(self) -> tuple[str, str, float]:
        import time

        inicio = time.monotonic()
        try:
            canal = await self._canal()
            queue = await canal.declare_queue(
                self.settings.rabbitmq_queue, durable=True, passive=True
            )
            mensajes = queue.declaration_result.message_count
            latencia = (time.monotonic() - inicio) * 1000
            return "ok", f"{mensajes} mensajes en cola", latencia
        except Exception as exc:
            return "error", f"RabbitMQ no disponible: {exc}", (time.monotonic() - inicio) * 1000

    async def close(self) -> None:
        if self._connection is not None and not self._connection.is_closed:
            await self._connection.close()
        self._connection = None
        self._channel = None
        self._queue = None

    async def esperar_conexion(self, intentos: int = 30, espera: float = 2.0) -> None:
        """Reintenta la conexión al arrancar el worker."""
        for intento in range(1, intentos + 1):
            try:
                await self.connect()
                return
            except QueueUnavailable as exc:
                logger.warning("RabbitMQ intento %s/%s: %s", intento, intentos, exc)
                if intento < intentos:
                    await asyncio.sleep(espera)
        raise QueueUnavailable("No se pudo conectar a RabbitMQ tras varios intentos")
