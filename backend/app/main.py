import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.admin import admin_router
from app.api.allocation import router as allocation_router
from app.api.coordinator import router as coordinator_router
from app.api.faculty import router as faculty_router
from app.api.hod import router as hod_router
from app.api.public import public_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.scheduler import shutdown_scheduler, start_scheduler

logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure room_blocks schema additions
    try:
        from app.core.database import engine
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE room_blocks ADD COLUMN IF NOT EXISTS is_released BOOLEAN NOT NULL DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE room_blocks ADD COLUMN IF NOT EXISTS released_at TIMESTAMP WITH TIME ZONE;"))
            conn.execute(text("ALTER TABLE room_blocks ADD COLUMN IF NOT EXISTS released_by INTEGER;"))
            conn.execute(text("ALTER TABLE room_blocks ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP;"))
    except Exception as e:
        logger.warning(f"Could not verify/patch room_blocks columns: {e}")

    # Startup: start APScheduler background jobs
    start_scheduler()
    yield
    # Shutdown: clean up background scheduler
    shutdown_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    description="Smart Classroom Allocation System API — Automated, intelligent college room management.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Attach slowapi rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Global unhandled exception handler to prevent leaking stack traces or credentials
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}", exc_info=True)
    if settings.APP_DEBUG and settings.APP_ENV != "production":
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": f"Internal server error: {str(exc)}"},
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."},
    )


# Security headers middleware
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.is_cookie_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# Configure CORS
origins = settings.BACKEND_CORS_ORIGINS
if isinstance(origins, list):
    allow_origins = [o for o in origins if o != "*"]
else:
    allow_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]

if not allow_origins:
    allow_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Include Authentication router under /api/auth as requested in spec
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])

# Include Admin router under /api/admin as requested in spec
app.include_router(admin_router, prefix="/api/admin")

# Include Coordinator router under /api/coordinator
app.include_router(coordinator_router, prefix="/api")

# Include Faculty router under /api/faculty
app.include_router(faculty_router, prefix="/api")

# Include HOD router under /api/hod
app.include_router(hod_router, prefix="/api")

# Include Public (no-login) router under /api/public as requested in spec
app.include_router(public_router, prefix="/api/public", tags=["Public"])

# Include Allocation router under /api/allocation
app.include_router(allocation_router, prefix="/api/allocation")

# Include versioned API routes under /api/v1
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(allocation_router, prefix=f"{settings.API_V1_PREFIX}/allocation")
app.include_router(public_router, prefix=f"{settings.API_V1_PREFIX}/public", tags=["Public"])
app.include_router(coordinator_router, prefix=f"{settings.API_V1_PREFIX}")
app.include_router(faculty_router, prefix=f"{settings.API_V1_PREFIX}")
app.include_router(hod_router, prefix=f"{settings.API_V1_PREFIX}")




@app.get("/", tags=["Root"])
def root():
    """Root status endpoint providing basic metadata and documentation links."""
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "version": "0.1.0",
        "docs_url": "/docs",
        "health_check": f"{settings.API_V1_PREFIX}/health",
    }
