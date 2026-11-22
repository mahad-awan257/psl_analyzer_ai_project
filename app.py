"""Streamlit dashboard: PSL Cricket Analytics and Fantasy Team Selector.

Run:  streamlit run app.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from psl_selector import config as C
from psl_selector.clustering import FEATURES, PlayerClusterer
from psl_selector.dataset import PlayerDataset
from psl_selector.problem import SelectionProblem
from psl_selector.selectors import BacktrackingSelector, GeneticSelector, GreedySelector

st.set_page_config(page_title="PSL Analytic Team Selector", layout="wide")


@st.cache_data
def load_players() -> pd.DataFrame:
    return PlayerDataset().df


@st.cache_data
def load_metadata() -> pd.DataFrame | None:
    return pd.read_csv(C.METADATA_CSV) if C.METADATA_CSV.exists() else None


df = load_players()
ds = PlayerDataset()
st.title("PSL Analytic Team Selector")
st.caption("Mahad Awan (24K-3014), Muhammad Basim Iftikhar (24K-3044) and Huzaifa Masood (24K-3049). "
           "AL-2002 Artificial Intelligence, FAST-NUCES Karachi, Fall 2026.")

tab_players, tab_profiles, tab_select, tab_exp = st.tabs(
    ["Players", "Player profiles", "Team selector", "Experiments"])

# --------------------------------------------------------------------- players
with tab_players:
    c1, c2, c3, c4 = st.columns(4)
    roles = c1.multiselect("Role", C.ROLES, default=C.ROLES, format_func=C.ROLE_NAMES.get)
    teams = c2.multiselect("Last PSL team", sorted(df.team.unique()))
    origin = c3.selectbox("Origin", ["All", "Local", "Overseas"])
    min_m = c4.slider("Minimum matches", int(df.matches.min()), int(df.matches.max()), int(df.matches.min()))
    view = df[df.role.isin(roles) & (df.matches >= min_m)]
    if teams:
        view = view[view.team.isin(teams)]
    if origin != "All":
        view = view[view.overseas == (origin == "Overseas")]
    cols = ["name", "role", "team", "overseas", "matches", "runs", "strike_rate", "bat_avg", "wickets",
            "economy", "catches", "points_per_match", "value", "credits", "profile"]
    st.dataframe(view[cols].sort_values("value", ascending=False), hide_index=True, width="stretch",
                 column_config={"value": st.column_config.NumberColumn("value", format="%.1f"),
                                "strike_rate": st.column_config.NumberColumn("strike rate", format="%.1f"),
                                "bat_avg": st.column_config.NumberColumn("bat avg", format="%.1f"),
                                "economy": st.column_config.NumberColumn("economy", format="%.2f"),
                                "points_per_match": st.column_config.NumberColumn("pts/match", format="%.1f")})
    a, b = st.columns(2)
    with a:
        st.subheader("Batting: strike rate against average")
        bat = view[view.balls_faced >= 60]
        st.scatter_chart(bat, x="bat_avg", y="strike_rate", color="role", size="runs")
    with b:
        st.subheader("Bowling: economy against wickets per match")
        bowl = view[view.legal_balls_bowled >= 60]
        st.scatter_chart(bowl, x="economy", y="wickets_per_match", color="role", size="wickets")
    meta = load_metadata()
    if meta is not None:
        with st.expander("Role and overseas metadata with evidence"):
            st.dataframe(meta, hide_index=True, width="stretch")

# -------------------------------------------------------------------- profiles
with tab_profiles:
    sil_path = C.PROCESSED_DIR / "silhouette_scores.csv"
    sil = pd.read_csv(sil_path) if sil_path.exists() else None
    default_k = int(sil[sil.chosen].k.iloc[0]) if sil is not None else 3
    k = st.slider("Number of clusters k", 2, 8, default_k,
                  help="Default k has the best silhouette score for k >= 3 (k = 2 just splits batters/bowlers).")
    prof = df if k == default_k else PlayerClusterer().fit_assign(df, k=k)
    a, b = st.columns([3, 2])
    with a:
        st.subheader("Profiles in PCA space")
        st.scatter_chart(prof, x="pc1", y="pc2", color="profile")
    with b:
        if sil is not None:
            st.subheader("Silhouette score by k")
            st.line_chart(sil.set_index("k").silhouette)
        st.caption("Profiles describe playing style. Team-rule roles come from the metadata and are checked separately.")
    st.subheader("Profile averages")
    st.dataframe(prof.groupby("profile")[FEATURES + ["value"]].mean().round(2), width="stretch")
    st.dataframe(prof.groupby("profile").name.apply(lambda s: ", ".join(s.head(12))).rename("examples"),
                 width="stretch")

# -------------------------------------------------------------------- selector
with tab_select:
    left, right = st.columns([1, 2.4])
    with left:
        st.subheader("Rules")
        budget = st.slider("Budget (credits)", 60.0, 121.0, C.DEFAULT_RULES["budget"], 0.5)
        max_ov = st.slider("Max overseas players", 0, 11, C.DEFAULT_RULES["max_overseas"])
        limits = {}
        for r, (lo, hi) in C.DEFAULT_RULES["role_limits"].items():
            limits[r] = st.slider(f"{C.ROLE_NAMES[r]}s", 0, 11, (lo, hi), key=f"lim_{r}")
        excluded = st.multiselect("Exclude players (injured / unavailable)", sorted(df.name))
        teams_pool = st.multiselect("Restrict pool to PSL teams (optional)", sorted(df.team.unique()))
        method = st.segmented_control("Method", ["Backtracking (exact)", "Genetic algorithm", "Greedy baseline",
                                                 "Compare all"], default="Backtracking (exact)", required=True, key="method")
        with st.expander("GA settings"):
            pop = st.number_input("Population", 10, 500, C.GA_DEFAULTS["population_size"])
            gens = st.number_input("Generations", 5, 1000, C.GA_DEFAULTS["generations"])
            mut = st.slider("Mutation rate", 0.0, 0.5, C.GA_DEFAULTS["mutation_rate"], 0.01)
            seed = st.number_input("Seed", 0, 10_000, C.SEED)
        go = st.button("Select XI", type="primary", width="stretch", key="select_xi")

    with right:
        pool_df = df[~df.name.isin(excluded)]
        if teams_pool:
            pool_df = pool_df[pool_df.team.isin(teams_pool)]
        problem = SelectionProblem(ds.players(pool_df), budget=budget, role_limits=limits, max_overseas=max_ov)
        st.caption(problem.describe())
        if go:
            sels = {"Backtracking (exact)": [BacktrackingSelector()],
                    "Genetic algorithm": [GeneticSelector(pop, gens, mut, seed=int(seed))],
                    "Greedy baseline": [GreedySelector()]}
            sels["Compare all"] = [s for v in sels.values() for s in v]
            results = []
            with st.spinner("Searching..."):
                for sel in sels[method]:
                    results.append(sel.select(problem))
            if len(results) > 1:
                st.subheader("Comparison")
                st.dataframe(pd.DataFrame([{"method": r.method, "valid": r.valid, "status": r.status,
                                            "score": round(r.score, 2), "cost": r.cost,
                                            "runtime_s": round(r.runtime_s, 4)} for r in results]),
                             hide_index=True, width="stretch")
            for r in results:
                st.subheader(r.method)
                if not r.valid:
                    st.error(f"No team satisfies the rules ({r.status}). Try a larger budget or looser limits."
                             if r.status == "infeasible" else f"No valid XI found ({r.status}).")
                    continue
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Team score", f"{r.score:.1f}")
                m2.metric("Credits used", f"{r.cost:.1f} / {budget:.1f}")
                m3.metric("Overseas", f"{sum(p.overseas for p in r.team)} / {max_ov}")
                m4.metric("Runtime", f"{r.runtime_s:.3f} s", r.status, delta_color="off")
                st.dataframe(pd.DataFrame([{**p.to_dict(), "runs": p.stats.get("runs"),
                                            "wickets": p.stats.get("wickets"),
                                            "matches": p.stats.get("matches")} for p in r.team])
                             [["name", "role", "team", "overseas", "credits", "value", "matches", "runs",
                               "wickets", "profile"]], hide_index=True, width="stretch")
                hist = r.info.get("history")
                if hist:
                    st.caption("GA best score by generation")
                    st.line_chart(pd.DataFrame(hist).set_index("generation")[["best", "mean_valid"]])
        else:
            st.caption("Set the rules on the left and press Select XI.")

# ----------------------------------------------------------------- experiments
with tab_exp:
    summary = C.RESULTS_DIR / "summary.csv"
    if not summary.exists():
        st.warning("Run `python scripts/run_experiments.py` to generate results.")
    else:
        st.subheader("Summary over 20 test cases (GA: seeds 42-51)")
        st.dataframe(pd.read_csv(summary), hide_index=True, width="stretch")
        figs = ["team_score_by_method.png", "runtime_by_pool_size.png", "ga_score_by_generation.png",
                "silhouette_scores.png", "player_profiles_pca.png"]
        for i in range(0, len(figs), 2):
            cols = st.columns(2)
            for c, f in zip(cols, figs[i:i + 2]):
                if (C.FIGURES_DIR / f).exists():
                    c.image(str(C.FIGURES_DIR / f))
        res = C.RESULTS_DIR / "experiment_results.csv"
        if res.exists():
            with st.expander("All runs"):
                st.dataframe(pd.read_csv(res), hide_index=True, width="stretch")

st.divider()
st.caption(f"Data: Cricsheet PSL ball-by-ball, seasons {', '.join(C.SEASONS)} (cricsheet.org). {len(df)} players "
           f"with at least {C.MIN_MATCHES} matches. Credits are simulated.")
