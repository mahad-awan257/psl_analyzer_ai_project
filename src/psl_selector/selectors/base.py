"""TeamSelector base class and the common result object."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..player import Player
from ..problem import SelectionProblem


@dataclass
class SelectionResult:
    """What a selector found, with its cost and time."""
    method: str
    team: list[Player] | None
    score: float
    cost: float
    runtime_s: float
    valid: bool
    status: str                     # "optimal", "feasible", "timeout", "infeasible", "failed"
    info: dict = field(default_factory=dict)

    def summary(self) -> str:
        """One-line description of the result."""
        if not self.valid:
            return f"{self.method}: no valid XI ({self.status}) in {self.runtime_s:.3f}s"
        return (f"{self.method}: score {self.score:.2f}, cost {self.cost:.1f}, "
                f"{self.status}, {self.runtime_s:.3f}s")


class TeamSelector(ABC):
    """Base class: subclasses override select_team()."""
    name = "base"

    def select(self, problem: SelectionProblem) -> SelectionResult:
        """Time ``select_team`` and wrap the output in a validated SelectionResult."""
        t0 = time.perf_counter()
        team, status, info = self.select_team(problem)
        dt = time.perf_counter() - t0
        valid = team is not None and problem.is_valid(team)
        if team is not None and not valid:
            info = {**info, "violations": problem.violations(team)}
            status = "failed"
        if valid:
            team = sorted(team, key=lambda p: (["WK", "BAT", "AR", "BOWL"].index(p.role), -p.value))
        return SelectionResult(self.name, team if valid else None,
                               problem.utility(team) if valid else 0.0,
                               problem.cost(team) if valid else 0.0, dt, valid, status, info)

    @abstractmethod
    def select_team(self, problem: SelectionProblem) -> tuple[list[Player] | None, str, dict]:
        """Return (team or None, status, extra info)."""
