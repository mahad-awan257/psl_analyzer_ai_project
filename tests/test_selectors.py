import itertools
import random

import pytest

from psl_selector.cricsheet import fantasy_points, parse_match
from psl_selector.experiments import brute_force
from psl_selector.player import Player
from psl_selector.problem import SelectionProblem
from psl_selector.selectors import BacktrackingSelector, GeneticSelector, GreedySelector


def make_pool(n=16, seed=0, roles=None):
    rng = random.Random(seed)
    roles = roles or (["WK"] * 2 + ["BAT"] * 5 + ["AR"] * 3 + ["BOWL"] * 6)
    pool = []
    for i in range(n):
        r = roles[i % len(roles)]
        pool.append(Player(f"p{i}", f"Player {i}", r, rng.random() < 0.35,
                           rng.choice([6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0, 10.5, 11.0]),
                           round(rng.uniform(20, 95), 2)))
    return pool


# ---------------------------------------------------------------- problem
def test_violations_detected():
    pool = make_pool()
    pr = SelectionProblem(pool, budget=100)
    assert "team size" in pr.violations(pool[:5])[0]
    assert any("duplicate" in v for v in pr.violations([pool[0]] * 11))


def test_can_complete_is_never_wrong_to_reject():
    """Forward checking must never reject a partial team that has a valid completion."""
    for seed in range(15):
        pool = make_pool(16, seed)
        pr = SelectionProblem(pool, budget=random.Random(seed).choice([70, 80, 90, 100]))
        valid = [c for c in itertools.combinations(pool, 11) if pr.is_valid(c)]
        assert pr.can_complete([], pool) or not valid
        for team in valid[:20]:
            for k in range(1, 11):
                part = list(team[:k])
                rest = [p for p in pool if p not in part]
                assert pr.can_complete(part, rest)


# --------------------------------------------------------------- selectors
@pytest.mark.parametrize("seed", range(10))
def test_backtracking_matches_brute_force(seed):
    pool = make_pool(16, seed)
    for budget in (75, 90, 100):
        pr = SelectionProblem(pool, budget=budget)
        _, exact = brute_force(pr)
        for sel in (BacktrackingSelector(), BacktrackingSelector(lagrangian=False),
                    BacktrackingSelector(use_bound=False, seed_greedy=False)):
            r = sel.select(pr)
            if exact is None:
                assert not r.valid and r.status == "infeasible"
            else:
                assert r.valid and r.status == "optimal"
                assert r.score == pytest.approx(exact)


@pytest.mark.parametrize("seed", range(5))
def test_greedy_and_ga_return_valid_or_none(seed):
    pool = make_pool(16, seed)
    pr = SelectionProblem(pool, budget=95)
    _, exact = brute_force(pr)
    for sel in (GreedySelector(), GeneticSelector(population_size=30, generations=30, seed=seed)):
        r = sel.select(pr)
        if r.valid:
            assert pr.is_valid(r.team)
            assert r.score <= exact + 1e-9


def test_infeasible_no_wicketkeeper():
    pool = make_pool(20, 1, roles=["BAT"] * 6 + ["AR"] * 4 + ["BOWL"] * 6)
    pr = SelectionProblem(pool, budget=200)
    for sel in (BacktrackingSelector(), GreedySelector(), GeneticSelector(generations=5)):
        r = sel.select(pr)
        assert not r.valid and r.team is None


def test_infeasible_budget():
    pool = make_pool(20, 2)
    pr = SelectionProblem(pool, budget=40)
    assert BacktrackingSelector().select(pr).status == "infeasible"


def test_overseas_limit_respected():
    pool = [Player(f"o{i}", f"O{i}", r, True, 7.0, 90.0) for i, r in
            enumerate(["WK", "BAT", "BAT", "AR", "BOWL", "BOWL"])]
    pool += make_pool(16, 3)
    pool = [Player(p.player_id, p.name, p.role, p.overseas if p.player_id.startswith("o") else False,
                   p.credits, p.value) for p in pool]
    pr = SelectionProblem(pool, budget=100, max_overseas=2)
    for sel in (BacktrackingSelector(), GreedySelector(), GeneticSelector(population_size=30, generations=30)):
        r = sel.select(pr)
        assert r.valid and sum(p.overseas for p in r.team) <= 2


def test_ga_seed_is_reproducible():
    pool = make_pool(16, 4)
    pr = SelectionProblem(pool, budget=90)
    a = GeneticSelector(population_size=20, generations=20, seed=42).select(pr)
    b = GeneticSelector(population_size=20, generations=20, seed=42).select(pr)
    assert a.score == b.score


# --------------------------------------------------------------- parsing
def test_fantasy_points_half_century():
    row = {"runs": 52, "balls_faced": 30, "fours": 5, "sixes": 2, "dismissed": 1, "wickets": 0,
           "bowled_lbw": 0, "maidens": 0, "legal_balls_bowled": 0, "runs_conceded": 0,
           "catches": 1, "stumpings": 0, "run_outs": 0}
    # 4 XI + 52 runs + 5 fours + 4 (sixes) + 8 fifty + 6 SR>170 + 8 catch
    assert fantasy_points(row) == 4 + 52 + 5 + 4 + 8 + 6 + 8


def test_parse_match_minimal():
    d = lambda bat, bowl, runs, **kw: {"batter": bat, "bowler": bowl, "non_striker": "B",
                                       "runs": {"batter": runs, "extras": 0, "total": runs}, **kw}
    match = {"info": {"season": "2026", "dates": ["2026-04-01"],
                      "players": {"X": ["A", "B"], "Y": ["C", "K"]},
                      "registry": {"people": {"A": "a1", "B": "b1", "C": "c1", "K": "k1"}}},
             "innings": [{"team": "X", "overs": [{"over": 0, "deliveries": [
                 d("A", "C", 4), d("A", "C", 6), d("A", "C", 0),
                 d("A", "C", 0, wickets=[{"player_out": "A", "kind": "stumped", "fielders": [{"name": "K"}]}]),
             ]}]}]}
    rows = {r["player"]: r for r in parse_match(match, "m1")}
    assert rows["A"]["runs"] == 10 and rows["A"]["fours"] == 1 and rows["A"]["sixes"] == 1
    assert rows["A"]["balls_faced"] == 4 and rows["A"]["dismissed"] == 1
    assert rows["C"]["wickets"] == 1 and rows["C"]["legal_balls_bowled"] == 4
    assert rows["K"]["stumpings"] == 1 and rows["K"]["kept_wicket"] == 1
    assert rows["A"]["player_id"] == "a1"
