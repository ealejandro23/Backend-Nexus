"""Acceso a PostgreSQL para perfiles, predicciones y campañas."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import asyncpg

from .config import Settings

logger = logging.getLogger(__name__)

ESTADOS_COMPRA = ("pagado", "completado", "entregado", "aprobado")


class Database:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._pool: asyncpg.Pool | None = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("La base de datos no está conectada")
        return self._pool

    async def connect(self, attempts: int = 10, delay: float = 2.0) -> None:
        ultimo_error: Exception | None = None
        for intento in range(1, attempts + 1):
            try:
                self._pool = await asyncpg.create_pool(
                    dsn=self.settings.database_dsn,
                    min_size=self.settings.db_pool_min_size,
                    max_size=self.settings.db_pool_max_size,
                    command_timeout=self.settings.db_timeout_seconds,
                )
                await self.ping()
                logger.info("Conectado a PostgreSQL (%s)", self.settings.db_host)
                return
            except Exception as exc:
                ultimo_error = exc
                logger.warning("PostgreSQL intento %s/%s: %s", intento, attempts, exc)
                if intento < attempts:
                    await asyncio.sleep(delay)
        raise RuntimeError(f"No se pudo conectar a PostgreSQL: {ultimo_error}")

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def ping(self) -> float:
        import time

        inicio = time.monotonic()
        async with self.pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return (time.monotonic() - inicio) * 1000

    async def ensure_schema(self) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS campanas (
                    id SERIAL PRIMARY KEY,
                    job_id UUID NOT NULL UNIQUE,
                    usuario_id VARCHAR(50) NOT NULL,
                    canal VARCHAR(50) NOT NULL,
                    asunto VARCHAR(200) NOT NULL,
                    mensaje TEXT NOT NULL,
                    recomendaciones JSONB NOT NULL DEFAULT '[]'::jsonb,
                    degradado BOOLEAN NOT NULL DEFAULT FALSE,
                    motivo_degradado VARCHAR(300),
                    modelo_llm VARCHAR(100),
                    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_campanas_usuario ON campanas(usuario_id, creado_en DESC)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_campanas_job ON campanas(job_id)"
            )

    async def get_usuario(self, usuario_id: str) -> dict[str, Any] | None:
        query = """
            SELECT
                u.usuario_id,
                u.edad,
                u.acepta_marketing,
                u.region,
                u.comuna,
                COALESCE((
                    SELECT COUNT(DISTINCT t.pedido_id)
                    FROM transacciones t
                    WHERE t.usuario_id = u.usuario_id
                      AND t.estado = ANY($2::text[])
                ), 0) AS frecuencia_compra,
                COALESCE((
                    SELECT AVG(t.total)
                    FROM transacciones t
                    WHERE t.usuario_id = u.usuario_id
                      AND t.estado = ANY($2::text[])
                ), 0) AS ticket_promedio
            FROM usuarios u
            WHERE u.usuario_id = $1
        """
        async with self.pool.acquire() as conn:
            fila = await conn.fetchrow(query, usuario_id, list(ESTADOS_COMPRA))
        if fila is None:
            return None
        return dict(fila)

    async def get_predicciones(
        self, usuario_id: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        query = """
            SELECT categoria, prediccion, propension
            FROM (
                SELECT DISTINCT ON (categoria)
                    categoria, prediccion, propension, fecha
                FROM predicciones
                WHERE usuario_id = $1
                ORDER BY categoria, fecha DESC
            ) ultimas
            ORDER BY prediccion DESC
            LIMIT $2
        """
        async with self.pool.acquire() as conn:
            filas = await conn.fetch(query, usuario_id, limit)
        return [dict(fila) for fila in filas]

    async def get_features_categoria(
        self, usuario_id: str, categoria: str
    ) -> dict[str, Any]:
        query = """
            SELECT
                COALESCE(COUNT(*) FILTER (
                    WHERE t.estado = ANY($3::text[])
                ), 0) AS num_compras_categoria,
                COALESCE(SUM(t.total) FILTER (
                    WHERE t.estado = ANY($3::text[])
                ), 0) AS total_gastado_categoria,
                COALESCE(
                    EXTRACT(EPOCH FROM (
                        NOW() - MAX(t.fecha) FILTER (
                            WHERE t.estado = ANY($3::text[])
                        )
                    )) / 86400,
                    999
                ) AS dias_ultima_compra
            FROM transacciones t
            JOIN productos p ON p.sku = t.sku
            WHERE t.usuario_id = $1 AND p.categoria = $2
        """
        async with self.pool.acquire() as conn:
            fila = await conn.fetchrow(
                query, usuario_id, categoria, list(ESTADOS_COMPRA)
            )
        if fila is None:
            return {
                "num_compras_categoria": 0,
                "total_gastado_categoria": 0.0,
                "dias_ultima_compra": 999,
            }
        datos = dict(fila)
        datos["num_vistas_categoria"] = 0
        datos["num_clics_categoria"] = 0
        datos["dias_ultima_compra"] = int(datos.get("dias_ultima_compra") or 999)
        return datos

    async def guardar_campana(self, campana: dict[str, Any]) -> None:
        query = """
            INSERT INTO campanas (
                job_id, usuario_id, canal, asunto, mensaje, recomendaciones,
                degradado, motivo_degradado, modelo_llm
            ) VALUES ($1::uuid, $2, $3, $4, $5, $6::jsonb, $7, $8, $9)
            ON CONFLICT (job_id) DO UPDATE SET
                asunto = EXCLUDED.asunto,
                mensaje = EXCLUDED.mensaje,
                recomendaciones = EXCLUDED.recomendaciones,
                degradado = EXCLUDED.degradado,
                motivo_degradado = EXCLUDED.motivo_degradado,
                modelo_llm = EXCLUDED.modelo_llm
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                query,
                campana["job_id"],
                campana["usuario_id"],
                campana["canal"],
                campana["asunto"][:200],
                campana["mensaje"],
                json.dumps(campana.get("recomendaciones", []), ensure_ascii=False),
                bool(campana.get("degradado", False)),
                (campana.get("motivo_degradado") or "")[:300] or None,
                campana.get("modelo_llm", ""),
            )

    async def get_ultima_campana(self, usuario_id: str) -> dict[str, Any] | None:
        query = """
            SELECT job_id, usuario_id, canal, asunto, mensaje, recomendaciones,
                   degradado, motivo_degradado, modelo_llm, creado_en
            FROM campanas
            WHERE usuario_id = $1
            ORDER BY creado_en DESC
            LIMIT 1
        """
        async with self.pool.acquire() as conn:
            fila = await conn.fetchrow(query, usuario_id)
        if fila is None:
            return None
        datos = dict(fila)
        recomendaciones = datos.get("recomendaciones")
        if isinstance(recomendaciones, str):
            try:
                datos["recomendaciones"] = json.loads(recomendaciones)
            except json.JSONDecodeError:
                datos["recomendaciones"] = []
        datos["job_id"] = str(datos["job_id"])
        return datos

    async def get_campana_por_job(self, job_id: str) -> dict[str, Any] | None:
        query = """
            SELECT job_id, usuario_id, canal, asunto, mensaje, recomendaciones,
                   degradado, motivo_degradado, modelo_llm, creado_en
            FROM campanas WHERE job_id = $1::uuid
        """
        async with self.pool.acquire() as conn:
            fila = await conn.fetchrow(query, job_id)
        if fila is None:
            return None
        datos = dict(fila)
        if isinstance(datos.get("recomendaciones"), str):
            try:
                datos["recomendaciones"] = json.loads(datos["recomendaciones"])
            except json.JSONDecodeError:
                datos["recomendaciones"] = []
        datos["job_id"] = str(datos["job_id"])
        return datos
