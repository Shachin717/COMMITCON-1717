import datetime as dt
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import BookingStatus, RequesterType, RoomBlockReason, RoomStatus, RoomType
from app.schemas.booking import BookingResponse
from app.schemas.public import TimetableResponse


class CoordinatorDecisionRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")
    note: Optional[str] = None


class CoordinatorBulkDecisionRequest(BaseModel):
    booking_ids: List[int] = Field(..., min_length=1)
    action: str = Field(..., pattern="^(approve|reject)$")
    note: Optional[str] = None


class CoordinatorBulkDecisionResponse(BaseModel):
    message: str
    success_count: int
    failed_count: int
    processed_ids: List[int]


class CoordinatorRoomBlockPreviewRequest(BaseModel):
    room_id: int
    date_from: date
    date_to: date
    slot_ids: Optional[List[int]] = None
    reason: RoomBlockReason = RoomBlockReason.MAINTENANCE


class AffectedBookingItem(BaseModel):
    booking_id: int
    reference: str
    requester_name: str
    requester_email: str
    date: date
    slot_id: int
    slot_label: str
    purpose: str
    expected_strength: int
    current_room_id: int
    current_room_name: str
    suggested_room_id: Optional[int] = None
    suggested_room_name: Optional[str] = None
    suggested_block_name: Optional[str] = None
    suggested_capacity: Optional[int] = None
    can_relocate: bool = False


class RoomBlockPreviewResponse(BaseModel):
    room_id: int
    room_name: str
    total_affected: int
    can_relocate_count: int
    cannot_relocate_count: int
    affected_bookings: List[AffectedBookingItem]


class ConfirmRelocationRequest(BaseModel):
    room_id: int
    date_from: date
    date_to: date
    slot_ids: Optional[List[int]] = None
    reason: RoomBlockReason = RoomBlockReason.MAINTENANCE
    note: Optional[str] = None
    mark_as_exam_hall: bool = False


class ConfirmRelocationResponse(BaseModel):
    message: str
    blocks_created: int
    relocated_count: int
    unresolved_count: int


class CoordinatorRoomBlockCreate(BaseModel):
    room_id: int
    date_from: date
    date_to: date
    slot_ids: Optional[List[int]] = None  # None or empty implies all slots for that day
    reason: RoomBlockReason = RoomBlockReason.MAINTENANCE
    note: Optional[str] = None
    mark_as_exam_hall: bool = False  # If True, temporarily/permanently update room_type to EXAM_HALL


class RoomBlockSummary(BaseModel):
    id: int
    room_id: int
    room_name: str
    date: date
    slot_id: Optional[int] = None
    slot_label: Optional[str] = None
    reason: RoomBlockReason
    note: Optional[str] = None
    created_by: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class RoomBlockBatchResponse(BaseModel):
    message: str
    created_count: int
    blocks: List[RoomBlockSummary]


class RoomOverviewItem(BaseModel):
    room_id: int
    room_name: str
    block_id: int
    block_name: str
    capacity: int
    room_type: RoomType
    is_booked: bool
    status: str  # FREE, BOOKED, MAINTENANCE, EXAM, CLASS
    booking_reference: Optional[str] = None
    purpose: Optional[str] = None
    is_my_block: bool = False


class BlockOverviewResponse(BaseModel):
    date: date
    slot_id: Optional[int] = None
    total_rooms: int
    booked_rooms_count: int
    free_rooms_count: int
    other_rooms_count: int  # maintenance, exam, class
    rooms: List[RoomOverviewItem]


class CoordinatorRoomResponse(BaseModel):
    id: int
    name: str
    block: str
    block_id: int
    floor: int
    room_type: RoomType
    capacity: int
    status: RoomStatus
    maintenance_note: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CoordinatorRoomsResponse(BaseModel):
    items: List[CoordinatorRoomResponse]
    total: int


class CoordinatorBlockResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CoordinatorBlocksResponse(BaseModel):
    items: List[CoordinatorBlockResponse]
    total: int


class BlockedRoomSummary(BaseModel):
    id: int
    name: str
    block: str
    block_id: int
    floor: int
    room_type: str
    type: str
    capacity: int

    model_config = ConfigDict(from_attributes=True)


class BlockedRoomItem(BaseModel):
    id: int
    is_indefinite: bool = False
    room_id: int
    room: BlockedRoomSummary
    date: Optional[dt.date] = None
    slot_id: Optional[int] = None
    slot_label: str
    reason: str
    note: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[dt.datetime] = None
    released_at: Optional[dt.datetime] = None
    released_by: Optional[str] = None
    is_released: bool = False
    status: str  # ACTIVE, UPCOMING, PAST, RELEASED

    model_config = ConfigDict(from_attributes=True)


class BlockedRoomsSummaryCounts(BaseModel):
    currently_blocked: int
    upcoming_blocks: int
    maintenance_rooms: int


class BlockedRoomsResponse(BaseModel):
    items: List[BlockedRoomItem]
    total: int
    page: int
    page_size: int
    pages: int
    summary: BlockedRoomsSummaryCounts


class RoomBlockBulkReleaseRequest(BaseModel):
    ids: Optional[List[int]] = None
    room_id: Optional[int] = None
    date_from: Optional[dt.date] = None
    date_to: Optional[dt.date] = None
    reason: Optional[RoomBlockReason] = None


class RoomBlockReleaseResponse(BaseModel):
    message: str
    block: BlockedRoomItem


class RoomBlockBulkReleaseResponse(BaseModel):
    message: str
    released_count: int
    released_ids: List[int]


class RoomMaintenanceReleaseResponse(BaseModel):
    message: str
    room_id: int
    room_name: str
    status: RoomStatus



