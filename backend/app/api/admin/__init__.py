from fastapi import APIRouter, Depends
from app.api.deps import require_roles
from app.models.enums import UserRole

from app.api.admin.audit_logs import router as audit_logs_router
from app.api.admin.blocks import router as blocks_router
from app.api.admin.bookings import router as bookings_router
from app.api.admin.departments import router as departments_router
from app.api.admin.facilities import router as facilities_router
from app.api.admin.overview import router as overview_router
from app.api.admin.rooms import router as rooms_router
from app.api.admin.time_slots import router as time_slots_router
from app.api.admin.timetable import router as timetable_router
from app.api.admin.users import router as users_router

admin_router = APIRouter(dependencies=[Depends(require_roles(UserRole.ADMIN))])

admin_router.include_router(overview_router)
admin_router.include_router(users_router)
admin_router.include_router(departments_router)
admin_router.include_router(blocks_router)
admin_router.include_router(facilities_router)
admin_router.include_router(rooms_router)
admin_router.include_router(time_slots_router)
admin_router.include_router(timetable_router)
admin_router.include_router(bookings_router)
admin_router.include_router(audit_logs_router)

__all__ = ["admin_router"]

