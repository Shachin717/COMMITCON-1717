from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Application operational status")
    version: str = Field(default="0.1.0", description="Application version")
    database: str = Field(default="connected", description="Database connection status")

