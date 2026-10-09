from app.optimizer.constraints import (
    SessionData,
    RoomData,
    TimeBlock,
    intervals_overlap,
    is_room_eligible_for_session,
)
from app.optimizer.objective import ObjectiveConfig
from app.optimizer.result_validator import AllocationResultValidator, ResultValidationError
from app.optimizer.solver import (
    OrToolsAllocationSolver,
    FirstFitBaselineSolver,
    OptimizationSolverResult,
)

__all__ = [
    "SessionData",
    "RoomData",
    "TimeBlock",
    "intervals_overlap",
    "is_room_eligible_for_session",
    "ObjectiveConfig",
    "AllocationResultValidator",
    "ResultValidationError",
    "OrToolsAllocationSolver",
    "FirstFitBaselineSolver",
    "OptimizationSolverResult",
]

