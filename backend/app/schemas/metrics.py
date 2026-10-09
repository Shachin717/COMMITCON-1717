from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AlgorithmMetrics(BaseModel):
    algorithm_name: str
    allocation_rate: float = Field(..., description="Percentage of eligible sessions allocated (0-100%)")
    seat_utilization: float = Field(..., description="Total students / Total assigned room capacity (0-100%)")
    room_occupancy_rate: float = Field(..., description="Percentage of available room time slots utilized")
    room_conflict_count: int = Field(0, description="Hard room conflict count (must be 0)")
    class_conflict_count: int = Field(0, description="Hard student group conflict count (must be 0)")
    preference_satisfaction_rate: float = Field(100.0, description="Percentage of soft preferences satisfied (0-100%)")
    runtime_ms: float = Field(..., description="Execution runtime in milliseconds")
    allocated_sessions: int
    unallocated_sessions: int
    total_eligible_sessions: int
    assignments_changed: Optional[int] = Field(None, description="Assignments altered from previous run")


class BenchmarkComparisonResponse(BaseModel):
    allocation_run_id: int
    optimizer_metrics: AlgorithmMetrics
    baseline_first_fit_metrics: AlgorithmMetrics
    comparison_summary: str
    is_optimizer_better_or_equal: bool

