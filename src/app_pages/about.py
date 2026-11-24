"""About page."""
import streamlit as st

from psl_selector import config as C
from ui.components import page_head, person_card
from ui.data import MEMBERS, players_df

page_head("About", "AL-2002 Artificial Intelligence, FAST-NUCES Karachi, Fall 2026")

st.subheader("Planned modules", anchor=False)
for col, (name, roll, work) in zip(st.columns(3, gap="medium"), MEMBERS):
    with col:
        person_card(name, roll, work)

st.markdown("Built with AI assistance from Claude Code. Details are in the project report.")
st.space("small")
a, b = st.columns(2, gap="large")
with a:
    st.subheader("Team rules", anchor=False)
    limits = C.DEFAULT_RULES["role_limits"]
    st.markdown("\n".join([
        f"- {C.DEFAULT_RULES['team_size']} players, {C.DEFAULT_RULES['budget']:g} credits",
        *[f"- {C.ROLE_NAMES[r]}s: " + (str(lo) if lo == hi else f"{lo} to {hi}") for r, (lo, hi) in limits.items()],
        f"- At most {C.DEFAULT_RULES['max_overseas']} overseas"]))
with b:
    st.subheader("Data", anchor=False)
    st.markdown(f"{len(players_df())} players with {C.MIN_MATCHES} or more matches, from [Cricsheet](https://cricsheet.org) "
                f"({C.SEASONS[0]} to {C.SEASONS[-1]}). Roles come from playing records, with a few corrections by hand. "
                "Past records do not predict future matches.")
    st.link_button("Code on GitHub", "https://github.com/mahad-awan257/psl_analyzer_ai_project")
