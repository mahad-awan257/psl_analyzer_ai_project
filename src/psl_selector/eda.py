"""Exploratory data analysis: cleaning, season leaders, role summaries and findings.

Rates from very few balls are unreliable (one boundary off two balls is a strike rate of 200),
so a season rate is kept only above a minimum sample. Remaining extremes are flagged with the
1.5 IQR rule and reported. They are genuine performances, so they are flagged, not deleted.
"""
from __future__ import annotations

import pandas as pd

from . import config as C

MIN_BALLS_FACED = 60     # per season, for a strike rate
MIN_BALLS_BOWLED = 60    # per season, for an economy rate


def load_player_matches() -> pd.DataFrame:
    """One row per player per match. Raises FileNotFoundError if the data is not prepared."""
    if not C.PLAYER_MATCH_CSV.exists():
        raise FileNotFoundError(f"{C.PLAYER_MATCH_CSV} missing; run `python src/prepare_data.py`")
    return pd.read_csv(C.PLAYER_MATCH_CSV)


def season_table(pm: pd.DataFrame) -> pd.DataFrame:
    """Per player and season totals and rates, with unreliable rates set to missing."""
    g = (pm.sort_values("date").groupby(["season", "player_id"])
         .agg(player=("player", "last"), team=("team", "last"), matches=("match_id", "nunique"),
              runs=("runs", "sum"), balls_faced=("balls_faced", "sum"), dismissals=("dismissed", "sum"),
              sixes=("sixes", "sum"), balls_bowled=("legal_balls_bowled", "sum"),
              conceded=("runs_conceded", "sum"), wickets=("wickets", "sum"),
              points=("fantasy_points", "sum")).reset_index())
    g["strike_rate"] = (100 * g.runs / g.balls_faced).where(g.balls_faced >= MIN_BALLS_FACED)
    g["economy"] = (6 * g.conceded / g.balls_bowled).where(g.balls_bowled >= MIN_BALLS_BOWLED)
    g["points_per_match"] = g.points / g.matches
    for col in ("strike_rate", "economy"):
        g[f"{col}_outlier"] = iqr_outliers(g[col])
    return g


def iqr_outliers(s: pd.Series) -> pd.Series:
    """True where a value lies outside the 1.5 IQR fences (missing values are never outliers)."""
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    return ((s < q1 - 1.5 * (q3 - q1)) | (s > q3 + 1.5 * (q3 - q1))).fillna(False)


LEADERS = {"Runs": ("runs", False), "Wickets": ("wickets", False),
           "Strike rate": ("strike_rate", False), "Economy": ("economy", True)}


def top_performers(table: pd.DataFrame, season: str, measure: str, n: int = 5) -> pd.DataFrame:
    """Best ``n`` players of a season on one of the LEADERS measures."""
    col, ascending = LEADERS[measure]
    d = table[table.season == season].dropna(subset=[col]).sort_values(
        [col, "points"], ascending=[ascending, False])
    return d.head(n)[["player", "team", "matches", col]].reset_index(drop=True)


def cleaning_report(table: pd.DataFrame) -> pd.DataFrame:
    """How many values were missing, unreliable or flagged, for the report."""
    n = len(table)
    return pd.DataFrame([
        {"check": "Player-season rows", "count": n},
        {"check": f"Strike rate not used (under {MIN_BALLS_FACED} balls)", "count": int(table.strike_rate.isna().sum())},
        {"check": f"Economy not used (under {MIN_BALLS_BOWLED} balls)", "count": int(table.economy.isna().sum())},
        {"check": "Strike-rate outliers flagged", "count": int(table.strike_rate_outlier.sum())},
        {"check": "Economy outliers flagged", "count": int(table.economy_outlier.sum())},
        {"check": "Duplicate player-season rows", "count": int(table.duplicated(["season", "player_id"]).sum())},
    ])


def league_rates(table: pd.DataFrame) -> pd.DataFrame:
    """League strike rate and economy per season, from totals (not an average of averages)."""
    g = table.groupby("season")[["runs", "balls_faced", "conceded", "balls_bowled"]].sum()
    return pd.DataFrame({"strike_rate": 100 * g.runs / g.balls_faced,
                         "economy": 6 * g.conceded / g.balls_bowled}).round(2).reset_index()


def role_summary(players: pd.DataFrame) -> pd.DataFrame:
    """Grouped summary of the eligible players by role."""
    g = players.groupby("role")
    t = g[["runs", "balls_faced", "legal_balls_bowled", "runs_conceded", "wickets"]].sum()
    return pd.DataFrame({"players": g.size(), "strike_rate": 100 * t.runs / t.balls_faced,
                         "economy": 6 * t.runs_conceded / t.legal_balls_bowled, "wickets": t.wickets,
                         "points_per_match": g.points_per_match.mean(),
                         "credits": g.credits.mean()}).round(2).reset_index()


def findings(table: pd.DataFrame, players: pd.DataFrame) -> list[str]:
    """Written findings, computed from the data so they cannot go out of date."""
    lg = league_rates(table)
    first, last = lg.iloc[0], lg.iloc[-1]
    roles = role_summary(players).set_index("role")
    out = [f"League strike rate went from {first.strike_rate:.1f} in {first.season} to {last.strike_rate:.1f} in "
           f"{last.season}, and economy from {first.economy:.2f} to {last.economy:.2f}."]
    for m, word in (("Runs", "runs"), ("Wickets", "wickets")):
        best = [(s, top_performers(table, s, m, 1).iloc[0]) for s in sorted(table.season.unique())]
        out.append(f"Most {word}: " + "; ".join(f"{s}, {r.player} ({int(r[LEADERS[m][0]])})" for s, r in best) + ".")
    ppm = roles.points_per_match
    out.append(f"All-rounders average {ppm['AR']:.1f} fantasy points per match, against {ppm['BAT']:.1f} for batters, "
               f"{ppm['BOWL']:.1f} for bowlers and {ppm['WK']:.1f} for wicketkeepers.")
    return out


def run(players: pd.DataFrame, results_dir=C.RESULTS_DIR, figures_dir=C.FIGURES_DIR) -> list[str]:
    """Write the EDA tables and figures and return the findings."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    results_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    table = season_table(load_player_matches())
    cleaning_report(table).to_csv(results_dir / "eda_cleaning.csv", index=False)
    league_rates(table).to_csv(results_dir / "eda_league_rates.csv", index=False)
    role_summary(players).to_csv(results_dir / "eda_role_summary.csv", index=False)
    pd.concat([top_performers(table, s, m).rename(columns={LEADERS[m][0]: "result"}).assign(season=s, measure=m)
               for s in sorted(table.season.unique()) for m in LEADERS]).round(2).to_csv(
        results_dir / "eda_season_leaders.csv", index=False)

    sns.set_theme(style="whitegrid", font_scale=0.95)
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    sns.boxplot(data=table, x="season", y="strike_rate", ax=ax[0], color="#7cc49a")
    ax[0].set(title=f"Strike rate by season ({MIN_BALLS_FACED}+ balls)", xlabel="Season", ylabel="Strike rate")
    sns.boxplot(data=table, x="season", y="economy", ax=ax[1], color="#7cc49a")
    ax[1].set(title=f"Economy by season ({MIN_BALLS_BOWLED}+ balls)", xlabel="Season", ylabel="Runs per over")
    fig.tight_layout()
    fig.savefig(figures_dir / "eda_rates_by_season.png", dpi=150)
    plt.close(fig)
    found = findings(table, players)
    (results_dir / "EDA_FINDINGS.md").write_text(
        "# Findings from the data\n\n" + "\n".join(f"- {f}" for f in found) + "\n", encoding="utf-8")
    return found
