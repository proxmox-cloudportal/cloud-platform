"""
Application configuration management using Pydantic Settings.
"""
from typing import Optional, List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

    # Application
    APP_NAME: str = "Cloud Platform API"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = Field(default="development", pattern="^(development|staging|production)$")
    DEBUG: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="info", pattern="^(debug|info|warning|error|critical)$")

    # CORS
    CORS_ORIGINS: str = Field(default="http://localhost:3000")

    def get_cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if isinstance(self.CORS_ORIGINS, str):
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
        return self.CORS_ORIGINS

    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = Field(default=20, ge=1, le=100)
    DATABASE_MAX_OVERFLOW: int = Field(default=10, ge=0, le=50)
    DATABASE_ECHO: bool = Field(default=False)

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_CACHE_EXPIRATION: int = Field(default=300, ge=60)  # 5 minutes

    # JWT Authentication
    JWT_SECRET_KEY: str = Field(min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, ge=5, le=60)
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1, le=30)

    # Password Hashing
    PASSWORD_BCRYPT_ROUNDS: int = Field(default=12, ge=10, le=14)

    # Proxmox (optional for development)
    PROXMOX_HOST: Optional[str] = None
    PROXMOX_USER: Optional[str] = None
    PROXMOX_TOKEN_NAME: Optional[str] = None
    PROXMOX_TOKEN_VALUE: Optional[str] = None
    PROXMOX_VERIFY_SSL: bool = Field(default=True)

    # Celery (Task Queue)
    CELERY_BROKER_URL: str = Field(default="amqp://guest:guest@localhost:5672//")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/1")

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, ge=10)

    # Pagination
    DEFAULT_PAGE_SIZE: int = Field(default=20, ge=1, le=100)
    MAX_PAGE_SIZE: int = Field(default=100, ge=10, le=1000)

    # File Upload
    MAX_UPLOAD_SIZE: int = Field(default=10_485_760)  # 10MB in bytes

    # Monitoring
    ENABLE_METRICS: bool = Field(default=True)
    METRICS_PORT: int = Field(default=9090, ge=1024, le=65535)


# Global settings instance
settings = Settings()
