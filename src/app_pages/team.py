"""Build XI page."""
import pandas as pd
import streamlit as st

from psl_selector import config as C
from psl_selector.accounts import AccountError
from psl_selector.selectors import BacktrackingSelector, GeneticSelector, GreedySelector
from ui.components import PLAYER_COLUMNS, field, page_head, with_origin
from ui.data import default_result, make_problem, players_df
from ui.session import accounts, current_user

OUTCOMES = {"optimal": "Proven best", "feasible": "Valid team", "timeout": "Time limit reached",
            "infeasible": "No team exists", "failed": "Got stuck"}
METHODS = ["Backtracking", "Genetic", "Greedy"]
df = players_df()

page_head("Build your XI")
left, right = st.columns([1, 1.9], gap="large")

with left:
    with st.form("rules", border=True):
        budget = st.slider("Budget (credits)", 60.0, 121.0, C.DEFAULT_RULES["budget"], 0.5, format="%.1f", key="budget")
        max_ov = st.slider("Most overseas players", 0, 11, C.DEFAULT_RULES["max_overseas"], key="max_ov")
        methods = st.pills("Methods", METHODS, selection_mode="multi", default=["Backtracking"], key="methods")
        excluded = st.multiselect("Leave out players", sorted(df.name), key="excluded")
        teams = st.multiselect("Only from these teams", sorted(df.team.unique()), placeholder="All teams", key="teams")
        with st.expander("Players per role"):
            limits = {r: st.slider(C.ROLE_NAMES[r] + "s", 0, 8, lim, key=f"lim_{r}")
                      for r, lim in C.DEFAULT_RULES["role_limits"].items()}
        with st.expander("Genetic algorithm settings"):
            pop = st.number_input("Population", 10, 500, C.GA_DEFAULTS["population_size"], key="ga_pop")
            gens = st.number_input("Generations", 5, 1000, C.GA_DEFAULTS["generations"], key="ga_gens")
            mut = st.slider("Mutation rate", 0.0, 0.5, C.GA_DEFAULTS["mutation_rate"], 0.01, key="ga_mut")
            seed = st.number_input("Seed", 0, 10_000, C.SEED, key="ga_seed")
        go = st.form_submit_button("Pick team", type="primary", width="stretch", key="pick")

with right:
    if go:
        if not methods:
            st.warning("Choose at least one method, then press Pick team.")
        else:
            pool = df[~df.name.isin(excluded)]
            if teams:
                pool = pool[pool.team.isin(teams)]
            problem = make_problem(pool, budget=budget, role_limits=limits, max_overseas=max_ov)
            build = {"Backtracking": BacktrackingSelector, "Greedy": GreedySelector,
                     "Genetic": lambda: GeneticSelector(int(pop), int(gens), mut, seed=int(seed))}
            with st.spinner("Searching for the best team"):
                found = [build[m]().select(problem) for m in METHODS if m in methods]
            # Kept in the session so the team stays when other controls change.
            st.session_state.team_results = (found, budget, max_ov)
    results, used_budget, used_ov = st.session_state.get(
        "team_results", ([default_result()], C.DEFAULT_RULES["budget"], C.DEFAULT_RULES["max_overseas"]))

    if len(results) > 1:
        st.dataframe(pd.DataFrame([{"Method": r.method, "Score": r.score if r.valid else None,
                                    "Credits": r.cost if r.valid else None, "Seconds": r.runtime_s,
                                    "Outcome": OUTCOMES[r.status]} for r in results]), hide_index=True,
                     column_config={"Score": st.column_config.NumberColumn(format="%.1f"),
                                    "Credits": st.column_config.NumberColumn(format="%.1f"),
                                    "Seconds": st.column_config.NumberColumn(format="%.3f")},
                     alt="Score, cost and time for each method")
        shown = st.segmented_control("Show team from", [r.method for r in results], default=results[0].method,
                                     required=True, key="shown_method")
        result = next((r for r in results if r.method == shown), results[0])
    else:
        result = results[0]

    if not result.valid:
        if result.status == "infeasible":
            st.error("No team fits these rules. Raise the budget, allow more players per role, or add teams.")
        elif result.method == "Greedy":
            st.warning("Greedy got stuck before filling the team. A team may still exist: try Backtracking.")
        else:
            st.warning("No team found before the search stopped. Try looser rules.")
    else:
        stats = st.container(horizontal=True, gap="medium", horizontal_alignment="distribute")
        stats.metric("Team score", f"{result.score:.1f}", width="content")
        stats.metric("Credits used", f"{result.cost:g} of {used_budget:g}", width="content")
        stats.metric("Overseas", f"{sum(p.overseas for p in result.team)} of {used_ov}", width="content")
        stats.metric("Search time", f"{result.runtime_s:.3f} s", width="content")
        if result.status == "optimal":
            st.success("Proven best team for these rules", icon=":material/check_circle:")
        elif result.status == "timeout":
            st.warning("Time limit reached. Best team found so far.")
        field(result.team)
        table = pd.DataFrame([{**p.to_dict(), **{k: p.stats.get(k) for k in ("matches", "runs", "wickets")}}
                              for p in result.team]).pipe(with_origin)
        cols = ["name", "role", "team", "credits", "value", "matches", "runs", "wickets"]
        st.dataframe(table[cols], hide_index=True, column_config=PLAYER_COLUMNS, height="content", alt="Selected team")
        user = current_user()
        if user:
            with st.form("save_team", border=False):
                row = st.container(horizontal=True, vertical_alignment="bottom")
                team_name = row.text_input("Team name", max_chars=40, key="team_name", placeholder="My XI")
                save = row.form_submit_button("Save team", type="primary", key="save_team_btn")
            if save:
                try:
                    accounts().save_team(user[0], team_name, result.method, result.score, result.cost,
                                         [p.player_id for p in result.team])
                except AccountError as err:
                    st.error(str(err))
                else:
                    st.toast("Team saved", icon=":material/check_circle:")
        with st.container(horizontal=True):
            st.download_button("Download team (CSV)", table[cols].to_csv(index=False), "psl_dugout_team.csv", "text/csv")
            if st.button("My teams", key="team_to_account"):
                st.switch_page("app_pages/account.py")
