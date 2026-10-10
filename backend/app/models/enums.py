import enum


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    HOD = "HOD"
    COORDINATOR = "COORDINATOR"
    FACULTY = "FACULTY"


class RoomType(str, enum.Enum):
    CLASSROOM = "CLASSROOM"
    LAB = "LAB"
    EXAM_HALL = "EXAM_HALL"
    SEMINAR_HALL = "SEMINAR_HALL"


class RoomStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    MAINTENANCE = "MAINTENANCE"


class RoomBlockReason(str, enum.Enum):
    MAINTENANCE = "MAINTENANCE"
    EXAM = "EXAM"
    OTHER = "OTHER"


class BookingStatus(str, enum.Enum):
    PENDING = "PENDING"
    COORDINATOR_APPROVED = "COORDINATOR_APPROVED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    RELOCATED = "RELOCATED"


class RequesterType(str, enum.Enum):
    STUDENT = "STUDENT"
    FACULTY = "FACULTY"

