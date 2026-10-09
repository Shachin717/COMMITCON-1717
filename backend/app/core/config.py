import os
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Smart Classroom Allocation System"
    
    # Database
    DATABASE_URL: str = "sqlite:///./classroom_allocation.db"
    
    # Security
    SECRET_KEY: str = "default-insecure-secret-key-change-in-production-32chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    
    # CORS
    FRONTEND_ORIGIN: str = "http://localhost:3000"
    
    # Optimization Engine Defaults
    SOLVER_TIME_LIMIT_SECONDS: float = 30.0
    SOLVER_RANDOM_SEED: int = 42
    SOLVER_NUM_WORKERS: int = 4
    
    # Configurable Soft Constraint Penalties (weights)
    WEIGHT_UNALLOCATED_SESSION: int = 100000   # Critical: maximize allocated sessions
    WEIGHT_SEAT_WASTE: int = 2                 # Penalty per unused seat
    WEIGHT_DEPARTMENT_PREFERENCE: int = 50     # Penalty when not in preferred building/zone
    WEIGHT_SPECIALIZED_LAB_WASTE: int = 200    # Penalty for assigning specialized lab to general session
    WEIGHT_REALLOCATION_CHANGE: int = 500      # Penalty for reassigning a session that was already allocated
    
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def cors_origins(self) -> List[str]:
        if not self.FRONTEND_ORIGIN:
            return ["*"]
        return [origin.strip() for origin in self.FRONTEND_ORIGIN.split(",") if origin.strip()]


settings = Settings()

