"""EDA: unreliable rates are dropped, outliers flagged and leaders ordered correctly."""
import pandas as pd

from psl_selector import eda


def rows():
    base = {"team": "T", "dismissed": 1, "sixes": 0, "fantasy_points": 10.0, "runs_conceded": 0,
            "legal_balls_bowled": 0, "wickets": 0, "season": "2026", "date": "2026-01-01", "match_id": "m1"}
    return pd.DataFrame([
        {**base, "player_id": "a", "player": "Tiny sample", "runs": 12, "balls_faced": 2},
        {**base, "player_id": "b", "player": "Steady", "runs": 90, "balls_faced": 60},
        {**base, "player_id": "c", "player": "Fast", "runs": 100, "balls_faced": 60},
        {**base, "player_id": "d", "player": "Bowler", "runs": 0, "balls_faced": 0,
         "legal_balls_bowled": 60, "runs_conceded": 70, "wickets": 4}])


def test_small_samples_have_no_rate():
    t = eda.season_table(rows()).set_index("player")
    assert pd.isna(t.strike_rate["Tiny sample"]) and t.strike_rate["Steady"] == 150
    assert t.economy["Bowler"] == 7


def test_leaders_are_sorted_and_skip_missing():
    t = eda.season_table(rows())
    assert list(eda.top_performers(t, "2026", "Strike rate").player) == ["Fast", "Steady"]
    assert eda.top_performers(t, "2026", "Wickets", 1).player[0] == "Bowler"


def test_iqr_outliers():
    s = pd.Series([10, 11, 12, 11, 10, 100, None])
    assert list(eda.iqr_outliers(s)) == [False] * 5 + [True, False]
