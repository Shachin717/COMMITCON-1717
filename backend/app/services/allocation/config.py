from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class AllocationWeights:
    """
    Configurable weights for soft constraints in the smart allocation optimizer.
    
    Attributes:
        wastage_weight: Penalty for unused capacity ratio ((capacity - strength) / capacity).
                        Higher value encourages tighter room fit. Default: 40.0.
        dept_ownership_weight: Penalty when a department-specific room is allocated to a different
                               department, or general room is used instead of department lab. Default: 20.0.
        block_match_weight: Penalty when room block differs from requester's preferred or department block.
                            Default: 20.0.
        distance_weight: Penalty for floor distance between assigned room and requested/home floor.
                         Default: 10.0.
        split_penalty_weight: Penalty for splitting consecutive slots for the same requester/group
                              across disparate rooms or different blocks. Default: 10.0.
    """
    wastage_weight: float = 40.0
    dept_ownership_weight: float = 20.0
    block_match_weight: float = 20.0
    distance_weight: float = 10.0
    split_penalty_weight: float = 10.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "wastage_weight": self.wastage_weight,
            "dept_ownership_weight": self.dept_ownership_weight,
            "block_match_weight": self.block_match_weight,
            "distance_weight": self.distance_weight,
            "split_penalty_weight": self.split_penalty_weight,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AllocationWeights":
        if not data:
            return cls()
        return cls(
            wastage_weight=float(data.get("wastage_weight", 40.0)),
            dept_ownership_weight=float(data.get("dept_ownership_weight", 20.0)),
            block_match_weight=float(data.get("block_match_weight", 20.0)),
            distance_weight=float(data.get("distance_weight", 10.0)),
            split_penalty_weight=float(data.get("split_penalty_weight", 10.0)),
        )

