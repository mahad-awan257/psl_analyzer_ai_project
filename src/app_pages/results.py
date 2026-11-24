"""Results page."""
import altair as alt
import streamlit as st

from psl_selector import config as C
from ui.components import GREEN, big_text, page_head
from ui.data import csv

page_head("Results", "The same 20 tests for every method.")
res = csv(str(C.RESULTS_DIR / "experiment_results.csv"))
summary = csv(str(C.RESULTS_DIR / "summary.csv"))
hist = csv(str(C.RESULTS_DIR / "ga_history.csv"))
if res is None or summary is None:
    st.warning("No results yet. Run `python src/run_experiments.py` to create them.")
    st.stop()

bt = res[res.method == "Backtracking"].set_index("case_id")
solvable = bt.index[bt.status != "infeasible"]
names = {"Backtracking": "Backtracking", "Genetic": "Genetic", "Greedy": "Greedy",
         "Backtracking (no Lagrangian bound)": "Backtracking, simple bound"}
table = summary.assign(method=summary.method.map(names), found=100 * summary.found_rate,
                       # Share of all solvable tests: a test with no team found counts as a miss.
                       best=100 * summary.best_rate)
st.dataframe(table[["method", "found", "best", "mean_gap_pct", "max_runtime_s"]],
             hide_index=True, alt="Summary of each method", column_config={
                 "method": "Method",
                 "found": st.column_config.NumberColumn("Found a team", format="%.0f%%"),
                 "best": st.column_config.NumberColumn("Best team", format="%.0f%%"),
                 "mean_gap_pct": st.column_config.NumberColumn("Average gap", format="%.1f%%"),
                 "max_runtime_s": st.column_config.NumberColumn("Slowest (s)", format="%.3f")})

st.space("medium")
st.subheader("Greedy against the best team", anchor=False)
greedy = res[(res.method == "Greedy") & res.case_id.isin(solvable)].copy()
greedy["best"] = greedy.case_id.map(bt.score)
greedy["gap"] = 100 * (greedy.best - greedy.score) / greedy.best
missed = greedy[greedy.score.isna()].case_id.astype(str).tolist()
bars = alt.Chart(greedy.dropna(subset="score")).mark_bar(cornerRadiusEnd=4, size=36, color=GREEN).encode(
    x=alt.X("case_id:O", title="Test case", axis=alt.Axis(labelAngle=0)),
    y=alt.Y("gap:Q", title="Below the best team (%)"),
    tooltip=[alt.Tooltip("case_id", title="Case"), alt.Tooltip("pool_size", title="Players"),
             alt.Tooltip("budget", title="Budget"), alt.Tooltip("score", title="Greedy", format=".1f"),
             alt.Tooltip("best", title="Best", format=".1f"), alt.Tooltip("gap", title="Gap (%)", format=".1f")],
).properties(height=270)
st.altair_chart(big_text(bars), width="stretch", alt="How far greedy falls below the best team in each case")
st.markdown("Backtracking and genetic: **always 0%**." + (f" Greedy found no team in cases {' and '.join(missed)}." if missed else ""))

a, b = st.columns(2, gap="large")
with a:
    st.subheader("Time by pool size", anchor=False)
    # Solvable cases only: unsolvable pools stop at once and would hide the real search time.
    rt = (res[res.method.isin(list(names)) & res.case_id.isin(solvable)]
          .assign(label=lambda d: d.method.map(names))
          .groupby(["label", "pool_size"], as_index=False).runtime_s.mean())
    order = list(names.values())
    line = alt.Chart(rt).mark_line(point=alt.OverlayMarkDef(size=60, filled=True), strokeWidth=2).encode(
        x=alt.X("pool_size:Q", title="Players to choose from"),
        y=alt.Y("runtime_s:Q", title="Seconds (log scale)", scale=alt.Scale(type="log"), axis=alt.Axis(tickCount=6)),
        color=alt.Color("label:N", title=None, scale=alt.Scale(domain=order, range=["#2a78d6", "#eb6834", "#1baa7a", "#4a3aa7"]),
                        legend=alt.Legend(orient="top", columns=2, labelLimit=240)),
        tooltip=[alt.Tooltip("label", title="Method"), alt.Tooltip("pool_size", title="Players"),
                 alt.Tooltip("runtime_s", title="Seconds", format=".4f")],
    ).properties(height=340)
    st.altair_chart(big_text(line), width="stretch", alt="Run time of each method as the player pool grows")
    st.markdown("The budget-aware bound cuts 30 seconds to about **0.01**.")
with b:
    st.subheader("Genetic algorithm progress", anchor=False)
    if hist is not None:
        case = bt.loc[solvable].pool_size.idxmax()
        h = (hist[(hist.case_id == case) & (hist.generation <= 30)]
             .groupby("generation", as_index=False).best.mean())
        best = float(bt.score[case])
        prog = alt.Chart(h).mark_line(strokeWidth=3, color=GREEN).encode(
            x=alt.X("generation:Q", title="Generation"),
            y=alt.Y("best:Q", title="Best team score", scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip("generation", title="Generation"), alt.Tooltip("best", title="Score", format=".1f")])
        rule = alt.Chart(alt.Data(values=[{"y": best}])).mark_rule(strokeDash=[5, 4], color="#55605a").encode(y="y:Q")
        st.altair_chart(big_text((prog + rule).properties(height=340)), width="stretch",
                        alt="Average best score by generation, reaching the proven best")
        st.markdown(f"Dashed line: proven best (**{best:.1f}**). Average of 10 runs.")

with st.expander("Every run"):
    st.dataframe(res, hide_index=True, alt="All experiment runs")
