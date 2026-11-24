"""Parse Cricsheet JSON match files into per-player, per-match statistics.

Each row of the output is one player in one match, with batting, bowling and
fielding counts plus fantasy points computed with a documented T20 scheme.
Players are keyed by their Cricsheet registry id, so name variants merge.
"""
from __future__ import annotations

import json
import zipfile
from collections import defaultdict
from pathlib import Path

# Dismissals that are not credited to the bowler.
NON_BOWLER_DISMISSALS = {"run out", "retired hurt", "retired out", "obstructing the field",
                         "retired not out", "timed out", "handled the ball"}


def _empty_row():
    """A zeroed statistics row for one player in one match."""
    return {
        "batted": 0, "runs": 0, "balls_faced": 0, "fours": 0, "sixes": 0, "dismissed": 0,
        "legal_balls_bowled": 0, "runs_conceded": 0, "wickets": 0, "bowled_lbw": 0,
        "dot_balls": 0, "maidens": 0, "catches": 0, "stumpings": 0, "run_outs": 0,
        "kept_wicket": 0,
    }


def fantasy_points(r: dict) -> float:
    """T20 fantasy-style points for one player-match row (Dream11-like, simplified)."""
    pts = 4.0  # playing XI
    # Batting
    runs, balls = r["runs"], r["balls_faced"]
    pts += runs + r["fours"] + 2 * r["sixes"]
    if runs >= 100:
        pts += 16
    elif runs >= 50:
        pts += 8
    elif runs >= 30:
        pts += 4
    if r["dismissed"] and runs == 0 and balls > 0:
        pts -= 2
    if balls >= 10:
        sr = 100.0 * runs / balls
        if sr > 170: pts += 6
        elif sr > 150: pts += 4
        elif sr >= 130: pts += 2
        elif sr < 50: pts -= 6
        elif sr < 60: pts -= 4
        elif sr <= 70: pts -= 2
    # Bowling
    w = r["wickets"]
    pts += 25 * w + 8 * r["bowled_lbw"] + 12 * r["maidens"]
    if w >= 5: pts += 16
    elif w >= 4: pts += 8
    elif w >= 3: pts += 4
    if r["legal_balls_bowled"] >= 12:
        econ = 6.0 * r["runs_conceded"] / r["legal_balls_bowled"]
        if econ < 5: pts += 6
        elif econ < 6: pts += 4
        elif econ <= 7: pts += 2
        elif econ > 12: pts -= 6
        elif econ > 11: pts -= 4
        elif econ >= 10: pts -= 2
    # Fielding
    pts += 8 * r["catches"] + (4 if r["catches"] >= 3 else 0)
    pts += 12 * r["stumpings"] + 6 * r["run_outs"]
    return pts


def parse_match(match: dict, match_id: str) -> list[dict]:
    """Statistics for every named player in one match (super overs excluded)."""
    info = match["info"]
    registry = info.get("registry", {}).get("people", {})
    season = str(info["season"])
    date = info["dates"][0]
    rows: dict[str, dict] = {}
    team_of: dict[str, str] = {}
    for team, names in info["players"].items():
        for name in names:
            rows[name] = _empty_row()
            team_of[name] = team

    def row(name):
        """Get or create the row for a player."""
        if name not in rows:  # substitute fielders etc.
            rows[name] = _empty_row()
            team_of[name] = None
        return rows[name]

    for inn in match.get("innings", []):
        if inn.get("super_over"):
            continue
        batting_team = inn["team"]
        keeper_this_innings = set()
        for over in inn.get("overs", []):
            over_runs = defaultdict(int)
            over_legal = defaultdict(int)
            for d in over["deliveries"]:
                extras = d.get("extras", {})
                batter, bowler = d["batter"], d["bowler"]
                b = row(batter)
                b["batted"] = 1
                row(d["non_striker"])["batted"] = 1
                bat_runs = d["runs"]["batter"]
                if "wides" not in extras:
                    b["balls_faced"] += 1
                b["runs"] += bat_runs
                if not d["runs"].get("non_boundary"):
                    if bat_runs == 4: b["fours"] += 1
                    elif bat_runs == 6: b["sixes"] += 1
                bw = row(bowler)
                conceded = d["runs"]["total"] - extras.get("byes", 0) - extras.get("legbyes", 0) \
                    - extras.get("penalty", 0)
                bw["runs_conceded"] += conceded
                over_runs[bowler] += conceded
                legal = "wides" not in extras and "noballs" not in extras
                if legal:
                    bw["legal_balls_bowled"] += 1
                    over_legal[bowler] += 1
                    if d["runs"]["total"] == 0:
                        bw["dot_balls"] += 1
                for wk in d.get("wickets", []):
                    kind = wk["kind"]
                    row(wk["player_out"])["dismissed"] = 1
                    if kind not in NON_BOWLER_DISMISSALS:
                        bw["wickets"] += 1
                        if kind in ("bowled", "lbw"):
                            bw["bowled_lbw"] += 1
                    fielders = [f.get("name") for f in wk.get("fielders", []) if f.get("name")]
                    if kind in ("caught",) and fielders:
                        row(fielders[0])["catches"] += 1
                    elif kind == "caught and bowled":
                        bw["catches"] += 1
                    elif kind == "stumped" and fielders:
                        row(fielders[0])["stumpings"] += 1
                        keeper_this_innings.add(fielders[0])
                    elif kind == "run out":
                        for f in fielders:
                            row(f)["run_outs"] += 1
            for bowler, legal_n in over_legal.items():
                if legal_n >= 6 and over_runs[bowler] == 0:
                    rows[bowler]["maidens"] += 1
        for k in keeper_this_innings:
            rows[k]["kept_wicket"] = 1

    out = []
    for name, r in rows.items():
        if team_of.get(name) is None:
            continue  # substitutes do not count as appearances
        r.update({
            "match_id": match_id, "season": season, "date": date,
            "player_id": registry.get(name, name), "player": name, "team": team_of[name],
        })
        r["fantasy_points"] = fantasy_points(r)
        out.append(r)
    return out


def iter_matches(zip_path: Path):
    """Yield (match id, parsed JSON) for each match in a Cricsheet zip."""
    with zipfile.ZipFile(zip_path) as zf:
        for n in sorted(zf.namelist()):
            if n.endswith(".json"):
                yield Path(n).stem, json.loads(zf.read(n))


def parse_psl_zip(zip_path: Path, seasons: list[str]) -> list[dict]:
    """Parse every match of the given seasons."""
    rows = []
    for match_id, m in iter_matches(zip_path):
        if str(m["info"]["season"]) in seasons:
            rows.extend(parse_match(m, match_id))
    return rows


def international_teams(zip_path: Path, player_ids: set[str]) -> dict[str, set[str]]:
    """Map registry id -> set of international teams the player has represented (T20Is)."""
    teams: dict[str, set[str]] = defaultdict(set)
    with zipfile.ZipFile(zip_path) as zf:
        for n in zf.namelist():
            if not n.endswith(".json"):
                continue
            info = json.loads(zf.read(n))["info"]
            reg = info.get("registry", {}).get("people", {})
            for team, names in info["players"].items():
                for name in names:
                    pid = reg.get(name)
                    if pid in player_ids:
                        teams[pid].add(team)
    return teams
