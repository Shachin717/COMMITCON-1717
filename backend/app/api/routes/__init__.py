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

__all__ = [
    "health_router",
    "departments_router",
    "buildings_router",
    "facilities_router",
    "classrooms_router",
    "schedules_router",
    "availability_router",
    "bookings_router",
    "allocations_router",
    "auth_router",
]

