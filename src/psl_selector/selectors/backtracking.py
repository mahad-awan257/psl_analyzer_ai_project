"""CSP backtracking with branch-and-bound for the best feasible XI.

Search: each node decides one undecided player (include x_i=1 first, then
exclude x_i=0). Players are grouped by role and sorted by value, so the
undecided players of a role always form a suffix of that role's list.

* Variable ordering (MRV): while some role is below its minimum, branch on
  the role with the fewest spare candidates (domain size minus deficit).
  Otherwise branch on the role whose next candidate has the highest value.
* Forward checking: after each decision, prune if a role can no longer reach
  its minimum, the XI cannot be filled, overseas/role maxima are broken, or the
  cheapest possible completion exceeds the remaining budget.
* Bound (Lagrangian relaxation of the budget): for any lambda >= 0,
      best completion value <= lambda * budget_left + max_S sum_{i in S}(v_i - lambda * c_i)
  where S ranges over completions that respect role minima/maxima. The inner
  max is solved greedily from each role's list sorted by v - lambda*c, so it
  is a prefix sum. lambda is chosen once at the root to minimise the bound
  (lambda = 0 gives the plain "ignore the budget" bound). Candidates are
  branched in the same v - lambda*c order. The greedy baseline seeds the
  incumbent.
A time limit returns the best XI found so far with status "timeout".
"""
from __future__ import annotations

import time

from .base import TeamSelector
from .greedy import GreedySelector
from .. import config as C
from ..problem import SelectionProblem


class BacktrackingSelector(TeamSelector):
    """Exact search with MRV, forward checking and a Lagrangian bound."""
    name = "Backtracking"

    def __init__(self, time_limit: float = C.TIME_LIMIT_S, use_bound: bool = True,
                 lagrangian: bool = True, seed_greedy: bool = True):
        """Configure the time limit, bound and starting team."""
        self.time_limit = time_limit
        self.use_bound = use_bound
        self.lagrangian = lagrangian
        self.seed_greedy = seed_greedy

    def select_team(self, problem: SelectionProblem):
        """Search for the best valid XI."""
        roles = list(problem.role_limits)
        lo = {r: problem.role_limits[r][0] for r in roles}
        hi = {r: problem.role_limits[r][1] for r in roles}
        size, budget, max_ov = problem.team_size, problem.budget, problem.max_overseas
        lam = self.best_lambda(problem) if (self.use_bound and self.lagrangian) else 0.0
        adj = lambda p: p.value - lam * p.credits
        cand = {r: sorted([p for p in problem.pool if p.role == r], key=lambda p: -adj(p)) for r in roles}
        vals = {r: [adj(p) for p in cand[r]] for r in roles}
        # cheap[r][j]: ascending credits of cand[r][j:], truncated to team size (for cost bound).
        cheap = {r: [sorted(p.credits for p in cand[r][j:])[:problem.team_size]
                     for j in range(len(cand[r]) + 1)] for r in roles}

        best = {"team": None, "score": float("-inf")}
        if self.seed_greedy:
            g = GreedySelector().select(problem)
            if g.valid:
                best = {"team": list(g.team), "score": g.score}
        stats = {"nodes": 0, "checks": 0, "backtracks": 0, "pruned_feasibility": 0, "pruned_bound": 0}
        deadline = time.perf_counter() + self.time_limit
        timed_out = False

        ptr = {r: 0 for r in roles}
        count = {r: 0 for r in roles}
        team = []

        def check_and_bound(cost, ov, value):
            """Forward check + optimistic bound. Returns bound or None if infeasible."""
            need = size - len(team)
            deficit = {r: max(0, lo[r] - count[r]) for r in roles}
            if sum(deficit.values()) > need:
                return None
            avail = 0
            must_cost, extra_cost = 0.0, []
            ub, extra_vals = value, []
            for r in roles:
                left = len(cand[r]) - ptr[r]
                room = hi[r] - count[r]
                if room < 0 or left < deficit[r]:
                    return None
                take = min(room, left)
                avail += take
                cr = cheap[r][ptr[r]]
                must_cost += sum(cr[:deficit[r]])
                extra_cost.extend(cr[deficit[r]:take])
                v = vals[r][ptr[r]:ptr[r] + take]
                ub += sum(v[:deficit[r]])
                extra_vals.extend(v[deficit[r]:])
            if avail < need:
                return None
            free = need - sum(deficit.values())
            extra_cost.sort()
            if cost + must_cost + sum(extra_cost[:free]) > budget + 1e-9:
                return None
            extra_vals.sort(reverse=True)
            return ub + sum(extra_vals[:free]) + lam * (budget - cost)

        def choose_role():
            """Variable ordering: MRV first, then the best next candidate."""
            need_roles = [r for r in roles if count[r] < lo[r]]
            if need_roles:  # MRV: fewest spare values first
                return min(need_roles, key=lambda r: (len(cand[r]) - ptr[r]) - (lo[r] - count[r]))
            open_roles = [r for r in roles if count[r] < hi[r] and ptr[r] < len(cand[r])]
            if not open_roles:
                return None
            return max(open_roles, key=lambda r: vals[r][ptr[r]])

        def search(cost, ov, value):
            """Decide one player, then recurse on include and exclude."""
            nonlocal timed_out
            stats["nodes"] += 1
            if stats["nodes"] % 2000 == 0 and time.perf_counter() > deadline:
                timed_out = True
            if timed_out:
                return
            if len(team) == size:
                if value > best["score"] + 1e-9:
                    best["team"], best["score"] = list(team), value
                return
            stats["checks"] += 1
            bound = check_and_bound(cost, ov, value)
            if bound is None:
                stats["pruned_feasibility"] += 1
                stats["backtracks"] += 1
                return
            if self.use_bound and bound <= best["score"] + 1e-9:
                stats["pruned_bound"] += 1
                stats["backtracks"] += 1
                return
            r = choose_role()
            if r is None:
                return
            p = cand[r][ptr[r]]
            ptr[r] += 1
            # Branch 1: include p (value ordering: best candidate first).
            if count[r] < hi[r] and cost + p.credits <= budget + 1e-9 and (not p.overseas or ov < max_ov):
                team.append(p)
                count[r] += 1
                search(cost + p.credits, ov + p.overseas, value + p.value)
                count[r] -= 1
                team.pop()
            # Branch 2: exclude p.
            search(cost, ov, value)
            ptr[r] -= 1

        search(0.0, 0, 0.0)
        info = {**stats, "time_limit": self.time_limit, "lambda": round(lam, 4)}
        if timed_out:
            return best["team"], "timeout", info
        if best["team"] is None:
            return None, "infeasible", info
        return best["team"], "optimal", info

    @staticmethod
    def _relaxed_bound(problem: SelectionProblem, lam: float) -> float:
        """Root Lagrangian bound for a given lambda (role limits kept, budget relaxed)."""
        total, extras, need = 0.0, [], problem.team_size
        for r, (lo, hi) in problem.role_limits.items():
            v = sorted((p.value - lam * p.credits for p in problem.pool if p.role == r), reverse=True)
            if len(v) < lo:
                return float("-inf")
            total += sum(v[:lo])
            extras.extend(v[lo:hi])
            need -= lo
        extras.sort(reverse=True)
        if len(extras) < need:
            return float("-inf")
        return total + sum(extras[:need]) + lam * problem.budget

    def best_lambda(self, problem: SelectionProblem) -> float:
        """Minimise the convex root bound over lambda with a grid then ternary search."""
        f = lambda l: self._relaxed_bound(problem, l)
        grid = [i * 0.5 for i in range(0, 41)]
        vals = [f(l) for l in grid]
        if vals[0] == float("-inf"):
            return 0.0
        i = min(range(len(grid)), key=vals.__getitem__)
        a, b = grid[max(i - 1, 0)], grid[min(i + 1, len(grid) - 1)]
        for _ in range(40):
            m1, m2 = a + (b - a) / 3, b - (b - a) / 3
            if f(m1) <= f(m2):
                b = m2
            else:
                a = m1
        return (a + b) / 2
