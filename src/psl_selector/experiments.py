"""ExperimentRunner: compare selectors on the same player pools and budgets.

Evaluation plan (proposal section 7):
* 20 test cases (pool, budget) generated with seed 42, including cases with no valid XI.
* Backtracking, greedy and GA on every case; GA repeated with seeds 42-51.
* Small cases are solved by exhaustive enumeration to confirm the exact optimum.
* 30-second time limit for each run.
* Metrics: team score, valid-team rate, runtime, gap to the optimum.
* Charts: team score by method, runtime by pool size, GA score by generation,
  plus silhouette scores and the PCA view of the K-means profiles.
"""
from __future__ import annotations

import itertools
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config as C
from .dataset import PlayerDataset
from .player import Player
from .problem import SelectionProblem
from .selectors import BacktrackingSelector, GeneticSelector, GreedySelector

GA_SEEDS = list(range(42, 52))
BRUTE_FORCE_MAX_POOL = 20


@dataclass
class TestCase:
    """One player pool and budget."""
    case_id: int
    pool: list[Player]
    budget: float
    note: str = ""
    max_overseas: int = C.DEFAULT_RULES["max_overseas"]

    def problem(self) -> SelectionProblem:
        """The selection problem for this case."""
        return SelectionProblem(self.pool, budget=self.budget, max_overseas=self.max_overseas)


def brute_force(problem: SelectionProblem):
    """Exhaustive search over all XIs (only for small pools)."""
    best, best_v = None, float("-inf")
    for combo in itertools.combinations(problem.pool, problem.team_size):
        if problem.is_valid(combo):
            v = problem.utility(combo)
            if v > best_v:
                best, best_v = list(combo), v
    return best, (best_v if best else None)


class ExperimentRunner:
    """Run every selector on the same seeded test cases."""

    def __init__(self, dataset: PlayerDataset | None = None, seed: int = C.SEED,
                 time_limit: float = C.TIME_LIMIT_S, ga_seeds=GA_SEEDS, ablation: bool = True):
        """Set the data, seed, time limit and GA seeds."""
        self.ds = dataset or PlayerDataset()
        self.seed = seed
        self.time_limit = time_limit
        self.ga_seeds = list(ga_seeds)
        self.ablation = ablation

    # -------------------------------------------------------------- cases
    def make_cases(self, n_cases: int = 20) -> list[TestCase]:
        """Build the seeded test cases, including two designed to have no valid XI."""
        rng = np.random.default_rng(self.seed)
        players = self.ds.players()
        n = len(players)
        sizes = [16, 18, 20, 25, 30, 40, 50, 60, 80, 100, n]  # <=20 also solved by brute force
        budgets = [75.0, 80.0, 85.0, 90.0, 95.0, 100.0]
        cases = []
        # Stratified random pools: a guaranteed core per role (so random pools are not
        # trivially infeasible), the rest drawn uniformly from the remaining players.
        core = {"WK": 2, "BAT": 5, "AR": 2, "BOWL": 5}
        for cid in range(n_cases - 2):
            size = sizes[cid % len(sizes)]
            budget = float(rng.choice(budgets))
            idx = set()
            for r, k in core.items():
                ids = [i for i, p in enumerate(players) if p.role == r]
                idx |= set(int(i) for i in rng.choice(ids, size=k, replace=False))
            rest = [i for i in range(n) if i not in idx]
            idx |= set(int(i) for i in rng.choice(rest, size=size - len(idx), replace=False))
            cases.append(TestCase(cid, [players[i] for i in sorted(idx)], budget, "stratified random pool"))
        # Designed infeasible cases.
        no_wk = [p for p in players if p.role != "WK"]
        idx = rng.choice(len(no_wk), size=40, replace=False)
        cases.append(TestCase(n_cases - 2, [no_wk[i] for i in sorted(idx)], 100.0, "no wicketkeeper (infeasible)"))
        cheapest = sorted(players, key=lambda p: p.credits)
        cases.append(TestCase(n_cases - 1, players, round(sum(p.credits for p in cheapest[:11]) - 1, 1),
                              "budget below the 11 cheapest players (infeasible)"))
        return cases

    # ---------------------------------------------------------------- run
    def run(self, n_cases: int = 20, verbose: bool = True):
        """Run all methods. Returns (results, GA histories)."""
        cases = self.make_cases(n_cases)
        rows, histories = [], []
        for case in cases:
            pr = case.problem()
            exact = None
            if len(case.pool) <= BRUTE_FORCE_MAX_POOL:
                t0 = time.perf_counter()
                _, exact = brute_force(pr)
                bf_time = time.perf_counter() - t0
            base = {"case_id": case.case_id, "pool_size": len(case.pool), "budget": case.budget,
                    "note": case.note, "exact_optimum": exact}
            runs = [("Backtracking", None, BacktrackingSelector(time_limit=self.time_limit)),
                    ("Greedy", None, GreedySelector())]
            if self.ablation:
                runs.append(("Backtracking (no Lagrangian bound)", None,
                             BacktrackingSelector(time_limit=self.time_limit, lagrangian=False)))
            runs += [("Genetic", s, GeneticSelector(seed=s, time_limit=self.time_limit)) for s in self.ga_seeds]
            for label, seed, sel in runs:
                r = sel.select(pr)
                rows.append({**base, "method": label, "seed": seed, "valid": r.valid, "status": r.status,
                             "score": r.score if r.valid else np.nan, "cost": r.cost if r.valid else np.nan,
                             "runtime_s": r.runtime_s, "nodes": r.info.get("nodes"),
                             "backtracks": r.info.get("backtracks"), "checks": r.info.get("checks")})
                if label == "Genetic":
                    for h in r.info.get("history", []):
                        histories.append({"case_id": case.case_id, "seed": seed, **h})
            if exact is not None:
                rows.append({**base, "method": "Brute force", "seed": None, "valid": True, "status": "optimal",
                             "score": exact, "cost": np.nan, "runtime_s": bf_time, "nodes": None})
            if verbose:
                cr = [x for x in rows if x["case_id"] == case.case_id]
                bt = next(x for x in cr if x["method"] == "Backtracking")
                ga = [x["score"] for x in cr if x["method"] == "Genetic"]
                gr = next(x for x in cr if x["method"] == "Greedy")
                print(f"case {case.case_id:2d} pool {len(case.pool):3d} budget {case.budget:5.1f} | "
                      f"BT {bt['score']:.2f} ({bt['status']}, {bt['runtime_s']:.3f}s) | "
                      f"greedy {gr['score']:.2f} | GA mean {np.nanmean(ga) if any(np.isfinite(ga)) else float('nan'):.2f}"
                      + (f" | exact {exact:.2f}" if exact is not None else ""))
        return pd.DataFrame(rows), pd.DataFrame(histories)

    # ------------------------------------------------------------- report
    @staticmethod
    def summarise(results: pd.DataFrame) -> pd.DataFrame:
        """Summary by method over the solvable cases."""
        bt = results[results.method == "Backtracking"].set_index("case_id")
        opt = bt.loc[bt.status == "optimal", "score"]
        res = results[results.method != "Brute force"].copy()
        res["gap_pct"] = [100 * (opt[c] - s) / opt[c] if c in opt.index and np.isfinite(s) else np.nan
                          for c, s in zip(res.case_id, res.score)]
        feasible_cases = set(bt.index[bt.status != "infeasible"])
        solvable = set(bt.index[bt.status != "infeasible"])
        sol = res[res.case_id.isin(solvable)]
        g = sol.groupby("method")
        # Runtime, gaps and success rates use solvable cases only. Unsolvable cases stop almost
        # at once, so including them would make every method look faster than it is.
        out = pd.DataFrame({
            "solvable_runs": g.size(),
            "found_rate": g.valid.mean(),
            "best_rate": g.gap_pct.apply(lambda d: (d < 1e-6).mean()),
            "mean_gap_pct": g.gap_pct.mean(),
            "max_gap_pct": g.gap_pct.max(),
            "mean_runtime_s": g.runtime_s.mean(),
            "max_runtime_s": g.runtime_s.max(),
            "timeouts": g.status.apply(lambda d: (d == "timeout").sum()),
            "mean_nodes": g.nodes.mean(),
            "mean_backtracks": g.backtracks.mean(),
            "no_team_correct": res[~res.case_id.isin(solvable)].groupby("method").valid.apply(lambda v: (~v).mean()),
        })
        return out.round(4)

    @staticmethod
    def plot(results: pd.DataFrame, histories: pd.DataFrame, players: pd.DataFrame, out_dir=C.FIGURES_DIR):
        """Draw the report charts."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        out_dir.mkdir(parents=True, exist_ok=True)
        colors = {"Backtracking": "#2a6fdb", "Genetic": "#e07b39", "Greedy": "#3a9d5d",
                  "Backtracking (no Lagrangian bound)": "#8a8f98", "Brute force": "#6b4fbb"}
        res = results[results.method != "Brute force"]
        feasible = res.groupby("case_id").valid.any()
        fc = feasible[feasible].index

        # 1. Team score by method (per feasible case, GA = mean over seeds with min-max bars).
        fig, ax = plt.subplots(figsize=(11, 4.5))
        methods = ["Backtracking", "Genetic", "Greedy"]
        w = 0.27
        for k, m in enumerate(methods):
            d = res[(res.method == m) & res.case_id.isin(fc)].groupby("case_id").score
            mean, lo, hi = d.mean(), d.min(), d.max()
            x = np.arange(len(fc)) + (k - 1) * w
            ax.bar(x, mean.reindex(fc), w, label=m, color=colors[m])
            if m == "Genetic":
                ax.errorbar(x, mean.reindex(fc), yerr=[(mean - lo).clip(lower=0).reindex(fc),
                                                    (hi - mean).clip(lower=0).reindex(fc)],
                            fmt="none", ecolor="#333", capsize=2, lw=0.8)
        ax.set_xticks(np.arange(len(fc)))
        ax.set_xticklabels([str(c) for c in fc])
        ax.set_xlabel("Test case")
        ax.set_ylabel("Team score (sum of player values)")
        ax.set_title("Team score by method (GA: mean of seeds 42-51, bars = min-max)")
        ax.legend(frameon=False)
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        fig.savefig(out_dir / "team_score_by_method.png", dpi=150)
        plt.close(fig)

        # 2. Runtime by pool size.
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for m in ["Backtracking", "Backtracking (no Lagrangian bound)", "Genetic", "Greedy"]:
            d = res[(res.method == m) & res.case_id.isin(fc)].groupby("pool_size").runtime_s.mean()
            if len(d):
                ax.plot(d.index, d.values, marker="o", label=m, color=colors[m])
        ax.set_yscale("log")
        ax.axhline(30, ls="--", color="#999", lw=1)
        ax.text(ax.get_xlim()[0], 33, " 30 s limit", color="#777", fontsize=8)
        ax.set_xlabel("Player pool size")
        ax.set_ylabel("Mean runtime (s, log scale)")
        ax.set_title("Runtime by pool size (solvable cases)")
        ax.legend(frameon=False, fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        fig.savefig(out_dir / "runtime_by_pool_size.png", dpi=150)
        plt.close(fig)

        # 3. GA convergence on the largest feasible case.
        if len(histories):
            big = res[res.case_id.isin(fc)].sort_values("pool_size").case_id.iloc[-1]
            h = histories[histories.case_id == big]
            fig, ax = plt.subplots(figsize=(7, 4.5))
            for s, d in h.groupby("seed"):
                ax.plot(d.generation, d.best, color=colors["Genetic"], alpha=0.35, lw=1)
            mean = h.groupby("generation").best.mean()
            ax.plot(mean.index, mean.values, color=colors["Genetic"], lw=2.2, label="GA best (mean of 10 seeds)")
            opt = res[(res.case_id == big) & (res.method == "Backtracking")].score.iloc[0]
            ax.axhline(opt, color=colors["Backtracking"], ls="--", label=f"Backtracking optimum ({opt:.1f})")
            ax.set_xlabel("Generation")
            ax.set_ylabel("Best team score")
            ax.set_title(f"GA score by generation (case {big}, {int(res[res.case_id == big].pool_size.iloc[0])} players)")
            ax.legend(frameon=False)
            ax.spines[["top", "right"]].set_visible(False)
            fig.tight_layout()
            fig.savefig(out_dir / "ga_score_by_generation.png", dpi=150)
            plt.close(fig)

        # 4. Silhouette scores.
        sil_path = C.PROCESSED_DIR / "silhouette_scores.csv"
        if sil_path.exists():
            sil = pd.read_csv(sil_path)
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.plot(sil.k, sil.silhouette, marker="o", color="#2a6fdb")
            ch = sil[sil.chosen]
            ax.scatter(ch.k, ch.silhouette, s=120, facecolors="none", edgecolors="#e07b39", lw=2,
                       label=f"chosen k={int(ch.k.iloc[0])}")
            ax.set_xlabel("k (number of clusters)")
            ax.set_ylabel("Silhouette score")
            ax.set_title("K-means cluster quality")
            ax.legend(frameon=False)
            ax.spines[["top", "right"]].set_visible(False)
            fig.tight_layout()
            fig.savefig(out_dir / "silhouette_scores.png", dpi=150)
            plt.close(fig)

        # 5. PCA view of the player profiles.
        if {"pc1", "pc2", "profile"} <= set(players.columns):
            fig, ax = plt.subplots(figsize=(7, 5))
            palette = ["#2a6fdb", "#e07b39", "#3a9d5d", "#6b4fbb", "#c43d5a", "#8a8f98", "#d1a82b", "#1f9aa6"]
            for k, (prof, d) in enumerate(players.groupby("profile")):
                ax.scatter(d.pc1, d.pc2, s=28, color=palette[k % len(palette)], label=prof, alpha=0.85)
            for _, r in players.nlargest(10, "value").iterrows():
                ax.annotate(r["name"], (r.pc1, r.pc2), fontsize=7, xytext=(3, 3), textcoords="offset points")
            ax.set_xlabel("PC1")
            ax.set_ylabel("PC2")
            ax.set_title("K-means player profiles (PCA projection)")
            ax.legend(frameon=False, fontsize=8)
            ax.spines[["top", "right"]].set_visible(False)
            fig.tight_layout()
            fig.savefig(out_dir / "player_profiles_pca.png", dpi=150)
            plt.close(fig)
