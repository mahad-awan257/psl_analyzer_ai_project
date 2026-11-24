"""Top performers by season and what the data shows (EDA)."""
import altair as alt
import streamlit as st

from psl_selector import eda
from ui.components import GREEN, big_text, page_head, ranking
from ui.data import players_df, season_table

page_head("Seasons", "Top performers in each PSL season.")
table = season_table()
if table is None:
    st.warning("Season data is missing. Run `python src/prepare_data.py` to create it.")
    st.stop()

seasons = sorted(table.season.unique())
season = st.segmented_control("Season", seasons, default=seasons[-1], required=True, key="season")
for col, measure in zip(st.columns(4, gap="large"), eda.LEADERS):
    with col:
        st.subheader(measure, anchor=False)
        top = eda.top_performers(table, season, measure)
        value = eda.LEADERS[measure][0]
        ranking(top.rename(columns={"player": "name", value: "value"}), bars=False,
                digits=0 if measure in ("Runs", "Wickets") else 1)
st.markdown(f"Strike rate and economy need at least {eda.MIN_BALLS_FACED} balls in the season.")

rates = eda.league_rates(table)
for col, (value, title) in zip(st.columns(2, gap="large"),
                               (("strike_rate", "League strike rate"), ("economy", "League economy"))):
    with col:
        st.subheader(title, anchor=False)
        chart = alt.Chart(rates).mark_line(strokeWidth=3, color=GREEN, point=alt.OverlayMarkDef(size=90, color=GREEN)).encode(
            x=alt.X("season:O", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y(f"{value}:Q", title=None, scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip("season", title="Season"), alt.Tooltip(f"{value}:Q", title=title, format=".2f")],
        ).properties(height=230)
        st.altair_chart(big_text(chart), width="stretch", alt=f"{title} for each season")

st.subheader("Findings", anchor=False)
st.markdown("\n".join(f"- {f}" for f in eda.findings(table, players_df())))
