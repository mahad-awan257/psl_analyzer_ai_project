"""PSL Dugout: site entry point (navigation bar, shared styling, footer).

Run:  streamlit run src/app.py
"""
from pathlib import Path

import streamlit as st

from psl_selector import config as C
from ui.components import CSS
from ui.page_info import page_info
from ui.login import login_screen
from ui.session import current_user, log_out, notify, show_notice, sync_cookie

st.set_page_config(page_title="PSL Dugout", page_icon=":material/sports_cricket:", layout="wide")
st.logo(Path(__file__).parent / "static" / "logo.svg", size="large")
st.html(CSS)

user = current_user()
page = st.navigation([
    st.Page("app_pages/home.py", title="Home", icon="", default=True, help="The best eleven at a glance."),
    st.Page("app_pages/team.py", title="Build XI", icon="", help="Set the rules and pick a team with each method."),
    st.Page("app_pages/players.py", title="Players", icon="", help="Search and compare player records."),
    st.Page("app_pages/seasons.py", title="Seasons", icon="", help="Top performers by season."),
    st.Page("app_pages/styles.py", title="Styles", icon="", help="Playing styles found by K-means."),
    st.Page("app_pages/results.py", title="Results", icon="", help="How the three methods compare."),
    st.Page("app_pages/about.py", title="About", icon="", help="The project, the data and the group."),
    st.Page("app_pages/account.py", title="Account", icon="", visibility="hidden", help="Your account and saved teams."),
], position="top" if user else "hidden")

if user:
    # A button, not a page: going back in the browser can never log someone out by accident.
    with st.container(key="logout_bar"):
        if st.button("Log out", key="logout"):
            log_out()
            notify("Logged out")
            st.rerun()
page_info(page.title if user else "Log in")
show_notice()
sync_cookie()
main = st.container(key="site_main")
# Filled first so the footer still shows when a page stops early.
with st.container(key="site_footer"):
    st.markdown("Data: [Cricsheet](https://cricsheet.org). Simulated credits. Student project, not affiliated with the PSL.")

with main:
    # No page runs until someone is logged in, whichever address was opened.
    if user:
        page.run()
    else:
        login_screen()
