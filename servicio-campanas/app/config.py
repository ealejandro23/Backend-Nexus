"""Configuración central del servicio de campañas.

Todas las variables se leen desde el entorno (o desde un archivo .env en
desarrollo). En el servidor EC2 el archivo .env se crea con permisos 600 y
nunca se versiona en el repositorio.
"""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import quote

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Aplicación
    # ------------------------------------------------------------------
    app_name: str = "nexo-campanas"
    app_version: str = "3.0.0"
    environment: str = "local"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8090

    # ------------------------------------------------------------------
    # Base de datos
    # ------------------------------------------------------------------
    db_host: str = "db"
    db_port: int = 5432
    db_name: str = "nexo"
    db_user: str = "nexo"
    db_password: str = "nexo123"
    database_url: str | None = None
    db_pool_min_size: int = 1
    db_pool_max_size: int = 5
    db_timeout_seconds: float = 5.0

    # ------------------------------------------------------------------
    # RabbitMQ
    # ------------------------------------------------------------------
    rabbitmq_host: str = "rabbitmq"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "nexo"
    rabbitmq_password: str = "nexo123"
    rabbitmq_vhost: str = "/"
    rabbitmq_url: str | None = None
    rabbitmq_queue: str = "campanas"
    rabbitmq_dlq: str = "campanas.dlq"
    rabbitmq_exchange: str = "campanas.dlx"
    rabbitmq_prefetch: int = 1
    rabbitmq_max_retries: int = 3
    rabbitmq_connect_timeout: float = 5.0

    # ------------------------------------------------------------------
    # NVIDIA LLM
    # ------------------------------------------------------------------
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "nvidia/nemotron-3.5-lightning-30b-a3b"
    llm_disable_thinking: bool = True
    llm_timeout_seconds: float = 20.0
    llm_max_wait_seconds: float = 30.0
    llm_max_retries: int = 3
    llm_backoff_seconds: float = 0.5
    llm_max_tokens: int = 512
    llm_temperature: float = 0.4
    llm_health_timeout_seconds: float = 5.0

    # ------------------------------------------------------------------
    # SageMaker (modelo de propensión)
    # ------------------------------------------------------------------
    aws_region: str = "us-east-1"
    sagemaker_endpoint_name: str = ""
    sagemaker_timeout_seconds: float = 4.0

    # ------------------------------------------------------------------
    # S3 (exportación de campañas)
    # ------------------------------------------------------------------
    s3_bucket: str = ""
    s3_prefix: str = "campanas"
    s3_export_enabled: bool = True

    # ------------------------------------------------------------------
    # Privacidad / anonimización
    # ------------------------------------------------------------------
    anonymization_salt: str = "nexo-ep3-local-salt"
    max_recomendaciones_prompt: int = 5

    # ------------------------------------------------------------------
    # Health y operación
    # ------------------------------------------------------------------
    health_timeout_seconds: float = 5.0
    queue_inline_fallback: bool = True

    @property
    def database_dsn(self) -> str:
        if self.database_url:
            return self.database_url
        user = quote(self.db_user, safe="")
        password = quote(self.db_password, safe="")
        return (
            f"postgresql://{user}:{password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def rabbitmq_dsn(self) -> str:
        if self.rabbitmq_url:
            return self.rabbitmq_url
        user = quote(self.rabbitmq_user, safe="")
        password = quote(self.rabbitmq_password, safe="")
        vhost = quote(self.rabbitmq_vhost, safe="")
        return f"amqp://{user}:{password}@{self.rabbitmq_host}:{self.rabbitmq_port}/{vhost}"

    @property
    def nvidia_chat_url(self) -> str:
        return f"{self.nvidia_base_url.rstrip('/')}/chat/completions"

    @property
    def nvidia_models_url(self) -> str:
        return f"{self.nvidia_base_url.rstrip('/')}/models"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
