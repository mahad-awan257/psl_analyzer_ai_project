"""PlayerDataset: download, clean and aggregate Cricsheet PSL data into a player pool.

Pipeline (``PlayerDataset.prepare``):
1. Parse ball-by-ball JSON for the configured seasons -> per player-match rows.
2. Aggregate per player (batting, bowling, fielding, fantasy points).
3. Derive role and overseas metadata with evidence, then apply manual overrides.
4. Score players (see ``scoring.py``) and assign simulated credits.
5. Cluster players into profiles (see ``clustering.py``).
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C
from .cricsheet import parse_psl_zip, international_teams
from .player import Player


def download(url: str, dest: Path) -> Path:
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url} -> {dest}")
    req = urllib.request.Request(url, headers={"User-Agent": "psl-selector/1.0"})
    with urllib.request.urlopen(req) as r, open(dest, "wb") as f:
        f.write(r.read())
    return dest


def aggregate(pm: pd.DataFrame) -> pd.DataFrame:
    """Per-player aggregates from per-match rows."""
    pm = pm.copy()
    pm["season_weight"] = pm["season"].map(C.SEASON_WEIGHTS).fillna(0.5)
    pm["weighted_points"] = pm["fantasy_points"] * pm["season_weight"]
    pm = pm.sort_values("date")
    g = pm.groupby("player_id")
    agg = g.agg(
        name=("player", "last"), team=("team", "last"), matches=("match_id", "nunique"),
        seasons=("season", lambda s: ",".join(sorted(set(s)))),
        innings=("batted", "sum"), runs=("runs", "sum"), balls_faced=("balls_faced", "sum"),
        fours=("fours", "sum"), sixes=("sixes", "sum"), dismissals=("dismissed", "sum"),
        legal_balls_bowled=("legal_balls_bowled", "sum"), runs_conceded=("runs_conceded", "sum"),
        wickets=("wickets", "sum"), dot_balls=("dot_balls", "sum"), maidens=("maidens", "sum"),
        catches=("catches", "sum"), stumpings=("stumpings", "sum"), run_outs=("run_outs", "sum"),
        matches_kept=("kept_wicket", "sum"), fantasy_points=("fantasy_points", "sum"),
        weighted_points=("weighted_points", "sum"), weight_sum=("season_weight", "sum"),
    )
    safe = lambda a, b: np.where(b > 0, a / np.maximum(b, 1e-9), np.nan)
    agg["bat_avg"] = safe(agg.runs, agg.dismissals.clip(lower=1))
    agg["strike_rate"] = safe(100 * agg.runs, agg.balls_faced)
    agg["boundary_pct"] = safe(100 * (agg.fours + agg.sixes), agg.balls_faced)
    agg["balls_per_match"] = agg.balls_faced / agg.matches
    agg["overs_per_match"] = agg.legal_balls_bowled / 6 / agg.matches
    agg["economy"] = safe(6 * agg.runs_conceded, agg.legal_balls_bowled)
    agg["bowl_sr"] = safe(agg.legal_balls_bowled, agg.wickets)
    agg["dot_pct"] = safe(100 * agg.dot_balls, agg.legal_balls_bowled)
    agg["wickets_per_match"] = agg.wickets / agg.matches
    agg["catches_per_match"] = agg.catches / agg.matches
    agg["points_per_match"] = agg.fantasy_points / agg.matches
    agg["weighted_ppm"] = agg.weighted_points / agg.weight_sum
    return agg.reset_index()


def derive_role(row) -> tuple[str, str]:
    """Return (role, evidence) from playing data."""
    if row.stumpings >= 1 and row.overs_per_match < 0.5:
        return "WK", f"{int(row.stumpings)} PSL stumping(s); kept in {int(row.matches_kept)} match(es)"
    if row.overs_per_match < 1.0:
        return "BAT", f"{row.overs_per_match:.2f} overs/match, {row.balls_per_match:.1f} balls faced/match"
    if row.balls_per_match >= 7.0:
        return "AR", f"{row.overs_per_match:.2f} overs/match and {row.balls_per_match:.1f} balls faced/match"
    return "BOWL", f"{row.overs_per_match:.2f} overs/match, {row.balls_per_match:.1f} balls faced/match"


def build_metadata(players: pd.DataFrame, t20i_zip: Path | None) -> pd.DataFrame:
    intl = international_teams(t20i_zip, set(players.player_id)) if t20i_zip and t20i_zip.exists() else {}
    rows = []
    for r in players.itertuples():
        role, role_ev = derive_role(r)
        teams = intl.get(r.player_id, set())
        teams_clean = sorted(t for t in teams if t != "ICC World XI")
        if not teams_clean:
            overseas, ov_ev = False, "No men's T20I record in Cricsheet; assumed Pakistani (check overrides)"
        elif "Pakistan" in teams_clean:
            overseas, ov_ev = False, "Played T20Is for Pakistan"
        else:
            overseas, ov_ev = True, "Played T20Is for " + ", ".join(teams_clean)
        rows.append({"player_id": r.player_id, "name": r.name, "role": role, "role_source": role_ev,
                     "overseas": overseas, "overseas_source": ov_ev,
                     "reference": f"https://cricsheet.org/register/ (id {r.player_id})"})
    meta = pd.DataFrame(rows)
    return apply_overrides(meta)


def apply_overrides(meta: pd.DataFrame, path: Path = C.OVERRIDES_CSV) -> pd.DataFrame:
    if not path.exists():
        return meta
    ov = pd.read_csv(path, dtype=str).fillna("")
    meta = meta.set_index("player_id")
    for r in ov.itertuples():
        if r.player_id not in meta.index:
            continue
        if r.role:
            meta.loc[r.player_id, ["role", "role_source"]] = [r.role, f"Manual override: {r.note}"]
        if r.overseas:
            meta.loc[r.player_id, ["overseas", "overseas_source"]] = [r.overseas.lower() == "true",
                                                                     f"Manual override: {r.note}"]
        if r.reference:
            meta.loc[r.player_id, "reference"] = r.reference
    return meta.reset_index()


class PlayerDataset:
    """Loads the processed player table and exposes it as ``Player`` objects."""

    def __init__(self, players_csv: Path = C.PLAYERS_CSV):
        self.path = Path(players_csv)
        if not self.path.exists():
            fallback = C.SAMPLE_PLAYERS_CSV
            if not fallback.exists():
                raise FileNotFoundError(f"{self.path} missing; run `python scripts/prepare_data.py`")
            print(f"[PlayerDataset] {self.path} not found, using bundled sample {fallback}")
            self.path = fallback
        self.df = pd.read_csv(self.path)

    # ------------------------------------------------------------------ build
    @staticmethod
    def prepare(seasons=C.SEASONS, min_matches=C.MIN_MATCHES, offline=False) -> pd.DataFrame:
        from .scoring import score_players
        from .clustering import PlayerClusterer

        if not offline:
            download(C.PSL_ZIP_URL, C.PSL_ZIP)
            download(C.T20I_ZIP_URL, C.T20I_ZIP)
        if not C.PSL_ZIP.exists():
            raise FileNotFoundError(f"{C.PSL_ZIP} missing and offline mode set")
        C.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        pm = pd.DataFrame(parse_psl_zip(C.PSL_ZIP, seasons))
        pm.to_csv(C.PLAYER_MATCH_CSV, index=False)
        agg = aggregate(pm)
        eligible = agg[agg.matches >= min_matches].copy()
        meta = build_metadata(eligible, C.T20I_ZIP)
        C.METADATA_DIR.mkdir(parents=True, exist_ok=True)
        meta.to_csv(C.METADATA_CSV, index=False)
        df = eligible.merge(meta[["player_id", "role", "overseas"]], on="player_id")
        df = score_players(df)
        df = PlayerClusterer().fit_assign(df)
        df = df.sort_values(["role", "value"], ascending=[True, False]).round(3)
        df.to_csv(C.PLAYERS_CSV, index=False)
        C.SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
        # Small offline sample: top players per role, enough for a valid XI.
        sample = df.groupby("role", group_keys=False).apply(lambda d: d.nlargest(10, "value"))
        sample.to_csv(C.SAMPLE_PLAYERS_CSV, index=False)
        print(f"Matches: {pm.match_id.nunique()} | players seen: {len(agg)} | eligible: {len(df)}")
        return df

    # ------------------------------------------------------------------ access
    def players(self, df: pd.DataFrame | None = None) -> list[Player]:
        df = self.df if df is None else df
        stat_cols = [c for c in df.columns if c not in
                     {"player_id", "name", "role", "overseas", "credits", "value", "team", "cluster", "profile"}]
        return [Player(player_id=str(r["player_id"]), name=r["name"], role=r["role"],
                       overseas=bool(r["overseas"]), credits=float(r["credits"]), value=float(r["value"]),
                       team=r.get("team", ""), cluster=int(r.get("cluster", -1)),
                       profile=str(r.get("profile", "")), stats={c: r[c] for c in stat_cols})
                for _, r in df.iterrows()]

    def sample_pool(self, size: int, rng: np.random.Generator) -> list[Player]:
        """Random sub-pool of ``size`` players (used by experiments)."""
        idx = rng.choice(len(self.df), size=min(size, len(self.df)), replace=False)
        return self.players(self.df.iloc[sorted(idx)])
