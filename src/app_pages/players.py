"""Players page."""
import altair as alt
import streamlit as st

from psl_selector import config as C
from ui.components import PLAYER_COLUMNS, page_head, role_scatter, with_origin
from ui.data import csv, players_df

df = players_df()
page_head("Players")

with st.container(horizontal=True, vertical_alignment="bottom"):
    search = st.text_input("Search by name", placeholder="Babar", key="p_search", width=220)
    teams = st.multiselect("Last team", sorted(df.team.unique()), placeholder="All teams", key="p_teams", width=300)
    origin = st.segmented_control("Origin", ["All", "Local", "Overseas"], default="All", required=True, key="p_origin")
roles = st.pills("Role", C.ROLES, selection_mode="multi", default=C.ROLES, format_func=C.ROLE_NAMES.get, key="p_roles")

view = df[df.role.isin(roles)]
if search:
    view = view[view.name.str.contains(search.strip(), case=False, regex=False)]
if teams:
    view = view[view.team.isin(teams)]
if origin != "All":
    view = view[view.overseas == (origin == "Overseas")]

if view.empty:
    st.info("No players match. Clear the search or add a role.")
    st.stop()

st.markdown(f"**{len(view)}** of {len(df)} players")
cols = ["name", "role", "team", "overseas", "matches", "runs", "strike_rate", "wickets", "economy", "value", "credits"]
st.dataframe(with_origin(view)[cols].sort_values("value", ascending=False), hide_index=True, column_config=PLAYER_COLUMNS,
             height=460, placeholder="-", alt="Player records")

a, b = st.columns(2, gap="large")
with a:
    st.subheader("Batting (60+ balls)", anchor=False)
    bat = view[view.balls_faced >= 60]
    if bat.empty:
        st.caption("No player here has faced 60 balls.")
    else:
        role_scatter(bat, "bat_avg:Q", "strike_rate:Q", "Batting average", "Strike rate",
                     [alt.Tooltip("runs", title="Runs"), alt.Tooltip("bat_avg:Q", title="Average", format=".1f"),
                      alt.Tooltip("strike_rate:Q", title="Strike rate", format=".1f")],
                     "Strike rate against batting average for each player")
with b:
    st.subheader("Bowling (60+ balls)", anchor=False)
    bowl = view[view.legal_balls_bowled >= 60]
    if bowl.empty:
        st.caption("No player here has bowled 60 balls.")
    else:
        role_scatter(bowl, "economy:Q", "wickets_per_match:Q", "Economy (runs per over)", "Wickets per match",
                     [alt.Tooltip("wickets", title="Wickets"), alt.Tooltip("economy:Q", title="Economy", format=".2f")],
                     "Wickets per match against economy for each player")

meta = csv(str(C.METADATA_CSV))
if meta is not None:
    with st.expander("Where roles come from"):
        st.dataframe(meta, hide_index=True, alt="Evidence for role and overseas status")
