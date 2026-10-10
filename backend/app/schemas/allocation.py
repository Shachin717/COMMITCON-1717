from datetime import date, datetime
from decimal import Decimal
import math
from typing import Any, Dict, List, Optional, Union
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import RoomType


def _clean_float(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        val = float(v)
        if math.isnan(val) or math.isinf(val):
            return default
        return round(val, 2)
    except (TypeError, ValueError):
        return default


def _clean_int(v: Any, default: int = 0) -> int:
    if v is None:
        return default
    try:
        if hasattr(v, "item"):
            v = v.item()
        return int(v)
    except (TypeError, ValueError):
        return default


def _parse_opt_date(v: Any) -> Optional[date]:
    if v is None or v == "":
        return None
    if isinstance(v, date):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        v = v.strip()
        if not v:
            return None
        return date.fromisoformat(v[:10])
    return v


class AllocationWeightsConfig(BaseModel):
    """Configurable weights for soft constraints in the optimizer."""
    wastage_weight: float = Field(40.0, description="Weight for seat wastage ratio penalty")
    dept_ownership_weight: float = Field(20.0, description="Weight for department-owned room matching penalty")
    block_match_weight: float = Field(20.0, description="Weight for block preference mismatch penalty")
    distance_weight: float = Field(10.0, description="Weight for floor/distance penalty")
    split_penalty_weight: float = Field(10.0, description="Weight for splitting requester slots across rooms/blocks")

    @field_validator("*", mode="before")
    @classmethod
    def clean_weight_floats(cls, v: Any) -> Any:
        return _clean_float(v, default=0.0)


class AllocationRequestItem(BaseModel):
    """Input request item for allocation simulation or application."""
    id: Optional[Union[int, str]] = None
    date: date
    slot_id: int
    expected_strength: int = Field(..., gt=0)
    room_type: Optional[RoomType] = RoomType.CLASSROOM
    required_facilities: List[str] = Field(default_factory=list)
    department_id: Optional[int] = None
    preferred_block_id: Optional[int] = None
    preferred_floor: Optional[int] = None
    roll_no: Optional[str] = None
    name: Optional[str] = "Requester"
    email: Optional[str] = "requester@college.edu"
    class_name: Optional[str] = "Class"
    phone: Optional[str] = "9876543210"
    purpose: Optional[str] = "Academic Session"
    created_at: Optional[datetime] = None

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, v: Any) -> Any:
        parsed = _parse_opt_date(v)
        return parsed if parsed is not None else date.today()

    @field_validator("required_facilities", mode="before")
    @classmethod
    def clean_facilities(cls, v: Any) -> List[str]:
        if isinstance(v, (set, tuple)):
            return list(v)
        if isinstance(v, list):
            return v
        return []

    model_config = ConfigDict(from_attributes=True)


class AllocationAssignment(BaseModel):
    """Outcome of allocating a single request."""
    request_id: Union[int, str]
    date: date
    slot_id: int
    expected_strength: int
    allocated: bool
    room_id: Optional[int] = None
    room_name: Optional[str] = None
    block_id: Optional[int] = None
    block_name: Optional[str] = None
    floor: Optional[int] = None
    capacity: Optional[int] = None
    reason_if_unallocated: Optional[str] = None
    cost: Optional[float] = None

    @field_validator("date", mode="before")
    @classmethod
    def parse_assignment_date(cls, v: Any) -> Any:
        parsed = _parse_opt_date(v)
        return parsed if parsed is not None else date.today()

    @field_validator("cost", mode="before")
    @classmethod
    def clean_cost(cls, v: Any) -> Optional[float]:
        if v is None:
            return None
        try:
            val = float(v)
            if math.isnan(val) or math.isinf(val):
                return None
            return round(val, 2)
        except (TypeError, ValueError):
            return None

    @field_validator("slot_id", "expected_strength", mode="before")
    @classmethod
    def clean_ints(cls, v: Any) -> int:
        return _clean_int(v)

    @field_validator("room_id", "block_id", "floor", "capacity", mode="before")
    @classmethod
    def clean_opt_ints(cls, v: Any) -> Optional[int]:
        if v is None:
            return None
        return _clean_int(v)

    model_config = ConfigDict(from_attributes=True)


class AllocationMetricsResponse(BaseModel):
    """Evaluation metrics for an allocation plan."""
    total_requests: int
    allocated_count: int
    unallocated_count: int
    allocation_rate_pct: float
    seat_utilization_pct: float
    average_wastage_pct: float
    facility_match_pct: float
    preference_satisfaction_pct: float
    conflict_count: int
    block_switch_count: int
    efficiency_score: float
    weights_breakdown: Dict[str, float]

    @field_validator(
        "total_requests", "allocated_count", "unallocated_count", "conflict_count", "block_switch_count",
        mode="before"
    )
    @classmethod
    def clean_metric_ints(cls, v: Any) -> int:
        return _clean_int(v)

    @field_validator(
        "allocation_rate_pct", "seat_utilization_pct", "average_wastage_pct",
        "facility_match_pct", "preference_satisfaction_pct", "efficiency_score",
        mode="before"
    )
    @classmethod
    def clean_metric_floats(cls, v: Any) -> float:
        return _clean_float(v)

    @field_validator("weights_breakdown", mode="before")
    @classmethod
    def clean_weights_breakdown(cls, v: Any) -> Dict[str, float]:
        if not isinstance(v, dict):
            return {}
        return {str(k): _clean_float(val) for k, val in v.items()}

    model_config = ConfigDict(from_attributes=True)


class SimulationResult(BaseModel):
    allocations: List[AllocationAssignment]
    metrics: AllocationMetricsResponse


class AllocationSimulateRequest(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    use_existing_bookings: bool = True
    generate_demo: bool = False
    demo_count: int = 25
    requests: Optional[List[AllocationRequestItem]] = None
    weights: Optional[AllocationWeightsConfig] = None

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def parse_dates(cls, v: Any) -> Optional[date]:
        return _parse_opt_date(v)

    @field_validator("demo_count", mode="before")
    @classmethod
    def parse_demo_count(cls, v: Any) -> int:
        return _clean_int(v, default=25)


class AllocationComparison(BaseModel):
    efficiency_score_delta: float
    seat_utilization_delta_pct: float
    average_wastage_reduction_pct: float
    facility_match_delta_pct: float
    preference_satisfaction_delta_pct: float
    unallocated_delta: int

    @field_validator(
        "efficiency_score_delta", "seat_utilization_delta_pct", "average_wastage_reduction_pct",
        "facility_match_delta_pct", "preference_satisfaction_delta_pct",
        mode="before"
    )
    @classmethod
    def clean_comp_floats(cls, v: Any) -> float:
        return _clean_float(v)

    @field_validator("unallocated_delta", mode="before")
    @classmethod
    def clean_comp_int(cls, v: Any) -> int:
        return _clean_int(v)


class AllocationSimulateResponse(BaseModel):
    date_range: Dict[str, Optional[str]]
    total_requests: int
    baseline: SimulationResult
    optimized: SimulationResult
    comparison: AllocationComparison
    wastage_distribution: Optional[List[Dict[str, Any]]] = None
    heatmap_matrix: Optional[List[Dict[str, Any]]] = None
    maintenance_rooms: Optional[List[Dict[str, Any]]] = None

    @field_validator("total_requests", mode="before")
    @classmethod
    def clean_total_requests(cls, v: Any) -> int:
        return _clean_int(v)


class AllocationApplyRequest(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    use_existing_bookings: bool = True
    requests: Optional[List[AllocationRequestItem]] = None
    weights: Optional[AllocationWeightsConfig] = None

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def parse_apply_dates(cls, v: Any) -> Optional[date]:
        return _parse_opt_date(v)


class AllocationApplyResponse(BaseModel):
    status: str
    total_requests: int
    applied_count: int
    unallocated_count: int
    metrics: AllocationMetricsResponse
    message: str

    @field_validator("total_requests", "applied_count", "unallocated_count", mode="before")
    @classmethod
    def clean_apply_ints(cls, v: Any) -> int:
        return _clean_int(v)


class AllocationHistoryItem(BaseModel):
    id: int
    created_at: datetime
    status: str
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    total_requests: int
    baseline_metrics: Dict[str, Any]
    optimized_metrics: Dict[str, Any]
    execution_time_ms: float

    @field_validator("total_requests", "id", mode="before")
    @classmethod
    def clean_history_ints(cls, v: Any) -> int:
        return _clean_int(v)

    @field_validator("execution_time_ms", mode="before")
    @classmethod
    def clean_history_float(cls, v: Any) -> float:
        return _clean_float(v)

    model_config = ConfigDict(from_attributes=True)


class ReallocationRequest(BaseModel):
    room_id: int
    reason: str = Field(..., description="Reason e.g. MAINTENANCE or EXAM")
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    slot_id: Optional[int] = None
    send_notifications: bool = True
    preview_only: bool = False



class RelocatedBookingSummary(BaseModel):
    booking_id: int
    reference: str
    requester_name: str
    requester_email: str
    date: date
    slot_id: int
    original_room_id: int
    original_room_name: str
    replacement_room_id: Optional[int] = None
    replacement_room_name: Optional[str] = None
    replacement_block_name: Optional[str] = None
    status: str
    email_sent: bool


class ReallocationResponse(BaseModel):
    affected_count: int
    relocated_count: int
    unresolved_count: int
    relocated_bookings: List[RelocatedBookingSummary]
    message: str

