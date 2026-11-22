"""Baseline: greedy value-per-credit selection with feasibility checks."""
from __future__ import annotations

from .base import TeamSelector
from ..problem import SelectionProblem


class GreedySelector(TeamSelector):
    name = "Greedy"

    def select_team(self, problem: SelectionProblem):
        order = sorted(problem.pool, key=lambda p: (-p.value_per_credit, -p.value))
        team = []
        for i, p in enumerate(order):
            if len(team) == problem.team_size:
                break
            candidate = team + [p]
            # Accept only if the XI can still be completed from the players not yet considered.
            if problem.can_complete(candidate, order[i + 1:]):
                team = candidate
        if len(team) != problem.team_size:
            return None, "infeasible" if not problem.can_complete([], problem.pool) else "failed", {}
        return team, "feasible", {}
