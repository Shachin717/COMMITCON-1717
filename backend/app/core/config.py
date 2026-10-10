from typing import List, Optional, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Smart Classroom Allocation System"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    BACKEND_PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"

    # CORS
    BACKEND_CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        default_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
        if isinstance(v, str) and not v.startswith("["):
            origins = [i.strip() for i in v.split(",") if i.strip()]
            valid = [o for o in origins if o != "*"]
            return valid if valid else default_origins
        elif isinstance(v, list):
            valid = [str(i).strip() for i in v if str(i).strip() and str(i).strip() != "*"]
            return valid if valid else default_origins
        return default_origins

    # Security & Tokens
    SECRET_KEY: str = "temporary-secret-key-for-development"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    COOKIE_SECURE: Optional[bool] = None  # If None, automatically True if APP_ENV == "production"
    COOKIE_SAMESITE: str = "lax"
    CSRF_PROTECTION_ENABLED: bool = True

    # Password Reset & OTP
    OTP_EXPIRE_MINUTES: int = 10
    OTP_MAX_ATTEMPTS: int = 5
    OTP_RESEND_COOLDOWN_SECONDS: int = 60

    # Rate Limiting
    RATE_LIMITING_ENABLED: bool = True
    LOGIN_RATE_LIMIT: str = "10/minute"
    OTP_RATE_LIMIT: str = "5/minute"
    PUBLIC_RATE_LIMIT: str = "60/minute"
    PUBLIC_BOOKING_RATE_LIMIT: str = "20/minute"

    # Background Jobs & Automation
    AUTO_RELEASE_NO_SHOW: bool = False
    NO_SHOW_GRACE_MINUTES: int = 20
    REMINDER_JOB_ENABLED: bool = True
    REMINDER_WINDOW_MINUTES: int = 60

    # PostgreSQL Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "smart_classroom"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@db:5432/smart_classroom"

    # Mailpit / SMTP
    SMTP_HOST: str = "mailpit"
    SMTP_PORT: int = 1025
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_TLS: bool = False
    MAIL_FROM: str = "no-reply@smartclassroom.edu"
    EMAILS_FROM_EMAIL: Optional[str] = None
    EMAILS_FROM_NAME: str = "Smart Classroom System"

    @field_validator("MAIL_FROM", mode="before")
    @classmethod
    def assemble_mail_from(cls, v: Optional[str], info) -> str:
        if v and str(v).strip():
            return str(v).strip()
        data = info.data if hasattr(info, "data") else {}
        fallback = data.get("EMAILS_FROM_EMAIL")
        if fallback and str(fallback).strip():
            return str(fallback).strip()
        return "no-reply@smartclassroom.edu"

    @property
    def is_cookie_secure(self) -> bool:
        if self.COOKIE_SECURE is not None:
            return self.COOKIE_SECURE
        return self.APP_ENV.lower() == "production"

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()

