from datetime import date, datetime
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.class_session import ClassSessionResponse
from app.schemas.classroom import ClassroomResponse

AllocationStatus = Literal["DRAFT", "PUBLISHED"]
AllocationRunStatus = Literal["PENDING", "RUNNING", "OPTIMAL", "FEASIBLE", "INFEASIBLE", "ERROR"]


class SolverSettings(BaseModel):
    time_limit_seconds: Optional[float] = Field(30.0, gt=0, le=300)
    random_seed: Optional[int] = Field(42)
    num_workers: Optional[int] = Field(4, gt=0)
    weight_unallocated: Optional[int] = Field(100000)
    weight_seat_waste: Optional[int] = Field(2)
    weight_preference: Optional[int] = Field(50)
    weight_reallocation_change: Optional[int] = Field(500)


class AllocationGenerateRequest(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    session_ids: Optional[List[int]] = Field(default=None, description="Explicit list of session IDs to allocate")
    settings: Optional[SolverSettings] = Field(default_factory=SolverSettings)
    preserve_published: bool = Field(True, description="Whether to avoid disturbing existing published allocations")


class AllocationItemResponse(BaseModel):
    id: int
    allocation_run_id: int
    class_session_id: int
    room_id: int
    status: AllocationStatus
    created_at: datetime
    updated_at: datetime
    class_session: Optional[ClassSessionResponse] = None
    classroom: Optional[ClassroomResponse] = None

    model_config = ConfigDict(from_attributes=True)


class AllocationRunResponse(BaseModel):
    id: int
    status: AllocationRunStatus
    objective_value: Optional[float] = None
    solver_runtime_ms: float
    allocated_sessions: int
    unallocated_sessions: int
    total_sessions: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    allocations: List[AllocationItemResponse] = Field(default_factory=list)
    unallocated_session_ids: List[int] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ReallocationSummary(BaseModel):
    run_id: int
    changed_count: int
    retained_count: int
    newly_allocated_count: int
    unallocated_count: int
    changed_session_ids: List[int] = Field(default_factory=list)
    allocation_run: AllocationRunResponse

