"""SelectionProblem: the CSP / optimisation model shared by all selectors.

Variables : x_i in {0,1} for each player i in the pool.
Constraints: sum x_i = team_size; sum cost_i x_i <= budget;
             role_min[r] <= #role r <= role_max[r]; #overseas <= max_overseas.
Utility   : sum value_i x_i (only feasible XIs are accepted).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from . import config as C
from .player import Player


@dataclass
class SelectionProblem:
    """The player pool, the rules and the utility."""
    pool: Sequence[Player]
    budget: float = C.DEFAULT_RULES["budget"]
    team_size: int = C.DEFAULT_RULES["team_size"]
    role_limits: dict = field(default_factory=lambda: dict(C.DEFAULT_RULES["role_limits"]))
    max_overseas: int = C.DEFAULT_RULES["max_overseas"]

    def __post_init__(self):
        """Validate the pool and fill in missing role limits."""
        self.pool = list(self.pool)
        ids = [p.player_id for p in self.pool]
        if len(set(ids)) != len(ids):
            raise ValueError("Player pool contains duplicate player ids")
        for r in C.ROLES:
            self.role_limits.setdefault(r, (0, self.team_size))

    # ---------------------------------------------------------------- checks
    def violations(self, team: Iterable[Player]) -> list[str]:
        """Every rule a team breaks, as messages."""
        team = list(team)
        v = []
        if len({p.player_id for p in team}) != len(team):
            v.append("duplicate players")
        if len(team) != self.team_size:
            v.append(f"team size {len(team)} != {self.team_size}")
        cost = sum(p.credits for p in team)
        if cost > self.budget + 1e-9:
            v.append(f"cost {cost:.1f} > budget {self.budget:.1f}")
        for r, (lo, hi) in self.role_limits.items():
            n = sum(p.role == r for p in team)
            if not lo <= n <= hi:
                v.append(f"{r} count {n} not in [{lo},{hi}]")
        ov = sum(p.overseas for p in team)
        if ov > self.max_overseas:
            v.append(f"overseas {ov} > {self.max_overseas}")
        return v

    def is_valid(self, team: Iterable[Player]) -> bool:
        """True if a team breaks no rule."""
        return not self.violations(team)

    @staticmethod
    def utility(team: Iterable[Player]) -> float:
        """Total value of a team."""
        return float(sum(p.value for p in team))

    @staticmethod
    def cost(team: Iterable[Player]) -> float:
        """Total credits of a team."""
        return float(sum(p.credits for p in team))

    # ------------------------------------------------- partial-team feasibility
    def can_complete(self, selected: Sequence[Player], remaining: Sequence[Player]) -> bool:
        """Forward check: can ``selected`` be extended with players from ``remaining``
        to a valid XI?  Uses necessary conditions only (fast, never rejects a
        completable state):
          * role and overseas maxima not exceeded, size not exceeded;
          * enough remaining players of each role to meet role minima;
          * enough players in total, respecting role maxima;
          * the cheapest completion that meets role minima fits the budget.
        """
        need_total = self.team_size - len(selected)
        if need_total < 0:
            return False
        counts = {r: 0 for r in self.role_limits}
        for p in selected:
            counts[p.role] = counts.get(p.role, 0) + 1
        if any(counts[r] > hi for r, (lo, hi) in self.role_limits.items()):
            return False
        ov = sum(p.overseas for p in selected)
        if ov > self.max_overseas:
            return False
        ov_left = self.max_overseas - ov
        spend_left = self.budget - sum(p.credits for p in selected)
        if spend_left < -1e-9:
            return False

        by_role: dict[str, list[Player]] = {r: [] for r in self.role_limits}
        for p in remaining:
            if p.role in by_role and (not p.overseas or ov_left > 0):
                by_role[p.role].append(p)
        deficit = {r: max(0, lo - counts[r]) for r, (lo, hi) in self.role_limits.items()}
        if sum(deficit.values()) > need_total:
            return False
        room = {r: hi - counts[r] for r, (lo, hi) in self.role_limits.items()}
        if sum(min(room[r], len(by_role[r])) for r in by_role) < need_total:
            return False
        # Cheapest completion: mandatory cheapest per role, then cheapest leftovers.
        must_cost, extras = 0.0, []
        for r, plist in by_role.items():
            plist = sorted(plist, key=lambda p: p.credits)
            if len(plist) < deficit[r]:
                return False
            must_cost += sum(p.credits for p in plist[:deficit[r]])
            extras.extend(plist[deficit[r]:room[r]])
        free = need_total - sum(deficit.values())
        extras.sort(key=lambda p: p.credits)
        if len(extras) < free:
            return False
        min_cost = must_cost + sum(p.credits for p in extras[:free])
        return min_cost <= spend_left + 1e-9

    def describe(self) -> str:
        """One-line summary of the rules."""
        lim = ", ".join(f"{r} {lo}-{hi}" for r, (lo, hi) in self.role_limits.items())
        return (f"{len(self.pool)} players | budget {self.budget} | {self.team_size} players | "
                f"{lim} | overseas <= {self.max_overseas}")
