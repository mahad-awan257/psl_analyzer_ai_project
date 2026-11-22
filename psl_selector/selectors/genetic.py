"""Genetic algorithm with tournament selection, set crossover, swap mutation,
elitism and a constraint-repair operator.

Chromosome: a set of ``team_size`` distinct pool indices.
Fitness   : team utility if the XI is valid; otherwise utility minus a large
            penalty per violated constraint, so invalid teams are effectively
            rejected by selection and never returned.
"""
from __future__ import annotations

import time

import numpy as np

from .base import TeamSelector
from .. import config as C
from ..problem import SelectionProblem

PENALTY = 1000.0


class GeneticSelector(TeamSelector):
    name = "Genetic"

    def __init__(self, population_size=C.GA_DEFAULTS["population_size"],
                 generations=C.GA_DEFAULTS["generations"], mutation_rate=C.GA_DEFAULTS["mutation_rate"],
                 crossover_rate=C.GA_DEFAULTS["crossover_rate"], tournament_size=C.GA_DEFAULTS["tournament_size"],
                 elitism=C.GA_DEFAULTS["elitism"], seed=C.SEED, time_limit=C.TIME_LIMIT_S):
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.tournament_size = tournament_size
        self.elitism = elitism
        self.seed = seed
        self.time_limit = time_limit

    # ----------------------------------------------------------- main loop
    def select_team(self, problem: SelectionProblem):
        self.rng = np.random.default_rng(self.seed)
        self.problem = problem
        self.pool = problem.pool
        self._cache = {}
        n = len(self.pool)
        if n < problem.team_size or not problem.can_complete([], self.pool):
            return None, "infeasible", {"history": []}
        self.by_role = {r: [i for i, p in enumerate(self.pool) if p.role == r] for r in problem.role_limits}

        pop = [self.repair(self.random_individual()) for _ in range(self.population_size)]
        fit = [self.fitness(ind) for ind in pop]
        history = []
        deadline = time.perf_counter() + self.time_limit
        best_ind, best_fit = None, float("-inf")
        status = "feasible"
        for gen in range(self.generations):
            order = np.argsort(fit)[::-1]
            if fit[order[0]] > best_fit:
                best_fit, best_ind = fit[order[0]], set(pop[order[0]])
            valid_fits = [f for f in fit if f > -PENALTY / 2]
            history.append({"generation": gen, "best": best_fit if best_fit > -PENALTY / 2 else np.nan,
                            "mean_valid": float(np.mean(valid_fits)) if valid_fits else np.nan,
                            "valid_share": len(valid_fits) / len(fit)})
            if time.perf_counter() > deadline:
                status = "timeout"
                break
            new_pop = [set(pop[i]) for i in order[:self.elitism]]
            while len(new_pop) < self.population_size:
                a, b = self.tournament(pop, fit), self.tournament(pop, fit)
                child = self.crossover(a, b) if self.rng.random() < self.crossover_rate else set(a)
                child = self.repair(self.mutate(child))
                new_pop.append(child)
            pop = new_pop
            fit = [self.fitness(ind) for ind in pop]
        i = int(np.argmax(fit))
        if fit[i] > best_fit:
            best_fit, best_ind = fit[i], set(pop[i])
        team = [self.pool[j] for j in best_ind] if best_ind is not None else None
        if team is None or not problem.is_valid(team):
            return None, "failed", {"history": history}
        return team, status, {"history": history, "evaluations": len(self._cache)}

    # ------------------------------------------------------------ operators
    def fitness(self, ind) -> float:
        key = frozenset(ind)
        if key not in self._cache:
            team = [self.pool[i] for i in key]
            v = self.problem.violations(team)
            self._cache[key] = self.problem.utility(team) - PENALTY * len(v)
        return self._cache[key]

    def random_individual(self) -> set:
        """Randomized constructive start: random order, keep players while completable."""
        order = self.rng.permutation(len(self.pool))
        team, chosen = [], set()
        for k, i in enumerate(order):
            if len(team) == self.problem.team_size:
                break
            cand = team + [self.pool[i]]
            rest = [self.pool[j] for j in order[k + 1:]]
            if self.problem.can_complete(cand, rest):
                team, chosen = cand, chosen | {int(i)}
        return chosen

    def tournament(self, pop, fit) -> set:
        idx = self.rng.choice(len(pop), size=self.tournament_size, replace=False)
        return pop[max(idx, key=lambda i: fit[i])]

    def crossover(self, a: set, b: set) -> set:
        """Keep players common to both parents; fill the rest from either parent at random."""
        child = set(a & b)
        rest = list((a | b) - child)
        self.rng.shuffle(rest)
        for i in rest:
            if len(child) >= self.problem.team_size:
                break
            child.add(i)
        return child

    def mutate(self, ind: set) -> set:
        ind = set(ind)
        for i in list(ind):
            if self.rng.random() < self.mutation_rate:
                role = self.pool[i].role
                same = [j for j in self.by_role[role] if j not in ind]
                options = same if same and self.rng.random() < 0.7 else \
                    [j for j in range(len(self.pool)) if j not in ind]
                if options:
                    ind.discard(i)
                    ind.add(int(self.rng.choice(options)))
        return ind

    def repair(self, ind: set) -> set:
        """Move an XI toward feasibility: size, role limits, overseas, budget."""
        P, pr = self.pool, self.problem
        ind = set(ind)
        vpc = lambda i: P[i].value_per_credit
        lims = pr.role_limits

        def role_count(r):
            return sum(P[i].role == r for i in ind)

        def overseas_count():
            return sum(P[i].overseas for i in ind)

        def addable(i):
            return i not in ind and (not P[i].overseas or overseas_count() < pr.max_overseas)

        for _ in range(3):
            # Role maxima.
            for r, (lo, hi) in lims.items():
                while role_count(r) > hi:
                    ind.discard(min((i for i in ind if P[i].role == r), key=vpc))
            # Role minima (make space from roles above their minimum).
            for r, (lo, hi) in lims.items():
                while role_count(r) < lo:
                    opts = [i for i in self.by_role[r] if addable(i)]
                    if not opts:
                        break
                    if len(ind) >= pr.team_size:
                        spare = [i for i in ind if role_count(P[i].role) > lims[P[i].role][0]]
                        if not spare:
                            break
                        ind.discard(min(spare, key=vpc))
                    ind.add(max(opts, key=vpc))
            # Size.
            while len(ind) > pr.team_size:
                spare = [i for i in ind if role_count(P[i].role) > lims[P[i].role][0]] or list(ind)
                ind.discard(min(spare, key=vpc))
            while len(ind) < pr.team_size:
                opts = [i for i in range(len(P)) if addable(i) and role_count(P[i].role) < lims[P[i].role][1]]
                if not opts:
                    break
                # Randomized among the best few to keep diversity.
                opts.sort(key=vpc, reverse=True)
                ind.add(int(opts[self.rng.integers(min(3, len(opts)))]))
            # Overseas: swap the weakest overseas player for a local of the same role.
            while overseas_count() > pr.max_overseas:
                ovs = sorted((i for i in ind if P[i].overseas), key=vpc)
                swapped = False
                for o in ovs:
                    locals_ = [j for j in self.by_role[P[o].role] if j not in ind and not P[j].overseas]
                    if locals_:
                        ind.discard(o)
                        ind.add(max(locals_, key=vpc))
                        swapped = True
                        break
                if not swapped:
                    break
            # Budget: swap for a cheaper same-role player losing least value per credit saved.
            while pr.cost(P[i] for i in ind) > pr.budget + 1e-9:
                best, best_ratio = None, float("inf")
                ov_full = overseas_count() >= pr.max_overseas
                for i in ind:
                    for j in self.by_role[P[i].role]:
                        if j in ind or P[j].credits >= P[i].credits:
                            continue
                        if P[j].overseas and not P[i].overseas and ov_full:
                            continue
                        ratio = (P[i].value - P[j].value) / (P[i].credits - P[j].credits)
                        if ratio < best_ratio:
                            best, best_ratio = (i, j), ratio
                if best is None:
                    break
                ind.discard(best[0])
                ind.add(best[1])
            if pr.is_valid([P[i] for i in ind]):
                break
        return ind
