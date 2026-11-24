"""Home page."""
import streamlit as st

from psl_selector import config as C
from ui.components import field, method_card, ranking
from ui.data import MEMBERS, default_result, players_df, summary_row

df = players_df()
best = default_result()

with st.container(key="hero"):
    text, pitch = st.columns([1, 1.2], gap="large", vertical_alignment="center")
    with text:
        st.title("The best PSL eleven for 100 credits", anchor=False)
        st.html('<p class="members">' + "<br>".join(f"{n}, {r}" for n, r, _ in MEMBERS) + "</p>")
        with st.container(horizontal=True, vertical_alignment="center"):
            if st.button("Build your XI", type="primary", key="cta_build"):
                st.switch_page("app_pages/team.py")
            if st.button("My teams", key="cta_teams"):
                st.switch_page("app_pages/account.py")
    with pitch:
        if best.valid:
            field(best.team)

with st.container(key="band"):
    st.header("Top players", anchor=False)
    for col, role in zip(st.columns(4, gap="large"), ["BAT", "BOWL", "AR", "WK"]):
        with col:
            st.subheader(C.ROLE_NAMES[role] + "s", anchor=False)
            ranking(df[df.role == role].nlargest(3, "value"))

with st.container(key="home_methods"):
    st.header("How often each method finds the best team", anchor=False)
    cards = [("Backtracking", "Backtracking", "Proven best, in milliseconds"),
             ("Genetic", "Genetic algorithm", "Evolves 100 teams at once"),
             ("Greedy", "Greedy", "Fastest, but can get stuck")]
    for col, (key, label, body) in zip(st.columns(3, gap="medium"), cards):
        row = summary_row(key)
        # Share of all solvable tests, so tests where no team was found count as misses.
        share = f"{row.best_rate:.0%}" if row is not None else "-"
        with col:
            method_card(label, share, body)
