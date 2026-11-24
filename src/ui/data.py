"""Cached data access shared by the site pages."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from psl_selector import config as C
from psl_selector import eda
from psl_selector.clustering import PlayerClusterer
from psl_selector.dataset import PlayerDataset
from psl_selector.problem import SelectionProblem
from psl_selector.selectors import BacktrackingSelector, SelectionResult

MEMBERS = [
    ("Mahad Awan", "24K-3014", "Data cleaning, scoring and K-means"),
    ("Muhammad Basim Iftikhar", "24K-3044", "Team rules, backtracking and greedy"),
    ("Huzaifa Masood", "24K-3049", "Genetic algorithm, interface and experiments"),
]


@st.cache_data
def players_df() -> pd.DataFrame:
    """The processed player table."""
    return PlayerDataset().df


@st.cache_data
def csv(path: str) -> pd.DataFrame | None:
    """A CSV file, or None if it does not exist."""
    try:
        return pd.read_csv(path)
    except FileNotFoundError:
        return None


@st.cache_data
def clustered(k: int) -> pd.DataFrame:
    """Players re-clustered into k styles."""
    return PlayerClusterer().fit_assign(players_df(), k=k)


@st.cache_data
def season_table() -> pd.DataFrame | None:
    """Per-season player table, or None if the match data is missing."""
    try:
        return eda.season_table(eda.load_player_matches())
    except FileNotFoundError:
        return None


@st.cache_data
def players_by_id() -> dict:
    """Player objects by id, for showing saved teams."""
    return {p.player_id: p for p in PlayerDataset().players()}


def make_problem(df: pd.DataFrame, **rules) -> SelectionProblem:
    """A selection problem from table rows."""
    return SelectionProblem(PlayerDataset().players(df), **rules)


@st.cache_data
def default_result() -> SelectionResult:
    """Best team under the default rules, used as the opening view."""
    return BacktrackingSelector().select(make_problem(players_df()))


def summary_row(method: str) -> pd.Series | None:
    """Summary row for one method, or None."""
    s = csv(str(C.RESULTS_DIR / "summary.csv"))
    if s is None or method not in set(s.method):
        return None
    return s.set_index("method").loc[method]
