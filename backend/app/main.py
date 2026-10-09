import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.core.exceptions import AppException
from app.database.connection import engine
from app.database.base import Base

# Routers
from app.api.routes.health import router as health_router
from app.api.routes.departments import router as departments_router
from app.api.routes.buildings import router as buildings_router
from app.api.routes.facilities import router as facilities_router
from app.api.routes.classrooms import router as classrooms_router
from app.api.routes.schedules import router as schedules_router
from app.api.routes.availability import router as availability_router
from app.api.routes.bookings import router as bookings_router
from app.api.routes.allocations import router as allocations_router
from app.api.routes.auth import router as auth_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
)
logger = logging.getLogger("classroom_allocation")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Smart Classroom Allocation System Backend...")
    # Create tables if not using migrations in dev mode
    Base.metadata.create_all(bind=engine)
    yield
    logger.info("Shutting down Smart Classroom Allocation System Backend...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Automated Constraint-Based Smart Classroom & Laboratory Allocation System API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Centralized Exception Handlers
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    logger.warning(f"Domain exception: {exc.detail} (Code: {exc.code})")
    content = {
        "success": False,
        "code": exc.code,
        "detail": exc.detail,
    }
    if exc.errors:
        content["errors"] = exc.errors
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.info(f"Schema validation error on {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "code": "VALIDATION_ERROR",
            "detail": "Input validation failed",
            "errors": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled server error on {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "code": "INTERNAL_SERVER_ERROR",
            "detail": "An internal server error occurred.",
        },
    )


from app.api.routes.hod import router as hod_router

# Register API v1 Routers
api_v1_router = FastAPI()
app.include_router(health_router, prefix=settings.API_V1_PREFIX)
app.include_router(departments_router, prefix=settings.API_V1_PREFIX)
app.include_router(buildings_router, prefix=settings.API_V1_PREFIX)
app.include_router(facilities_router, prefix=settings.API_V1_PREFIX)
app.include_router(classrooms_router, prefix=settings.API_V1_PREFIX)
app.include_router(schedules_router, prefix=settings.API_V1_PREFIX)
app.include_router(availability_router, prefix=settings.API_V1_PREFIX)
app.include_router(bookings_router, prefix=settings.API_V1_PREFIX)
app.include_router(allocations_router, prefix=settings.API_V1_PREFIX)
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(hod_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Root"])
def root():
    return {
        "message": "Welcome to the Smart Classroom Allocation System API",
        "version": "1.0.0",
        "docs": "/docs",
        "api_v1": settings.API_V1_PREFIX,
    }

