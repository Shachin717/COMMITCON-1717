from app.schemas.department import DepartmentCreate, DepartmentUpdate, DepartmentResponse
from app.schemas.building import BuildingCreate, BuildingUpdate, BuildingResponse
from app.schemas.facility import FacilityCreate, FacilityUpdate, FacilityResponse
from app.schemas.classroom import (
    ClassroomCreate,
    ClassroomUpdate,
    ClassroomResponse,
    LabAccessUpdate,
    ClassroomFacilityAdd,
)
from app.schemas.class_group import ClassGroupCreate, ClassGroupUpdate, ClassGroupResponse
from app.schemas.class_session import (
    ClassSessionCreate,
    ClassSessionUpdate,
    ClassSessionResponse,
    TimeSlotCreate,
    TimeSlotResponse,
)
from app.schemas.booking import (
    BookingCreate,
    BookingUpdate,
    BookingResponse,
    RoomUnavailabilityCreate,
    RoomUnavailabilityResponse,
    UnavailabilityConflictCheckResponse,
)
from app.schemas.allocation import (
    AllocationGenerateRequest,
    AllocationRunResponse,
    AllocationItemResponse,
    ReallocationSummary,
    SolverSettings,
)
from app.schemas.availability import (
    AvailabilityQuery,
    AvailabilityResponse,
    AvailableRoomItem,
)
from app.schemas.metrics import AlgorithmMetrics, BenchmarkComparisonResponse
from app.schemas.user import UserLogin, TokenResponse, UserCreate, UserResponse

__all__ = [
    "DepartmentCreate",
    "DepartmentUpdate",
    "DepartmentResponse",
    "BuildingCreate",
    "BuildingUpdate",
    "BuildingResponse",
    "FacilityCreate",
    "FacilityUpdate",
    "FacilityResponse",
    "ClassroomCreate",
    "ClassroomUpdate",
    "ClassroomResponse",
    "LabAccessUpdate",
    "ClassroomFacilityAdd",
    "ClassGroupCreate",
    "ClassGroupUpdate",
    "ClassGroupResponse",
    "ClassSessionCreate",
    "ClassSessionUpdate",
    "ClassSessionResponse",
    "TimeSlotCreate",
    "TimeSlotResponse",
    "BookingCreate",
    "BookingUpdate",
    "BookingResponse",
    "RoomUnavailabilityCreate",
    "RoomUnavailabilityResponse",
    "UnavailabilityConflictCheckResponse",
    "AllocationGenerateRequest",
    "AllocationRunResponse",
    "AllocationItemResponse",
    "ReallocationSummary",
    "SolverSettings",
    "AvailabilityQuery",
    "AvailabilityResponse",
    "AvailableRoomItem",
    "AlgorithmMetrics",
    "BenchmarkComparisonResponse",
    "UserLogin",
    "TokenResponse",
    "UserCreate",
    "UserResponse",
]

