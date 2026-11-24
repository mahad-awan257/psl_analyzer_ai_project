"""Saved teams and account settings."""
import pandas as pd
import streamlit as st

from psl_selector.accounts import AccountError
from ui.components import field, page_head
from ui.data import players_by_id
from ui.session import accounts, current_token, current_user, log_out, notify

store = accounts()
user = current_user()
if user is None:  # app.py already blocks this page; this is a second check
    st.stop()
uid, name = user
page_head(name, "Your account")
st.header("My teams", anchor=False)

teams = store.teams(uid)
if not teams:
    st.info("No saved teams yet. Build one and press Save team.")
    if st.button("Build a team", type="primary", key="build_first"):
        st.switch_page("app_pages/team.py")
else:
    st.dataframe(pd.DataFrame([{"Team": t["name"], "Method": t["method"], "Score": t["score"],
                                "Credits": t["cost"],
                                "Saved": pd.Timestamp(t["created"], unit="s", tz="UTC")} for t in teams]),
                 hide_index=True, alt="Saved teams", column_config={
                     "Score": st.column_config.NumberColumn(format="%.1f"),
                     "Credits": st.column_config.NumberColumn(format="%.1f"),
                     "Saved": st.column_config.DatetimeColumn(format="D MMM YYYY")})
    labels = {t["id"]: t["name"] for t in teams}
    pick = st.selectbox("Show team", list(labels), format_func=labels.get, key="saved_pick")
    team = next(t for t in teams if t["id"] == pick)
    known = players_by_id()
    shown = [known[p] for p in team["player_ids"] if p in known]
    if len(shown) < len(team["player_ids"]):
        st.warning("Some players are no longer in the data.")
    field(shown)
    if st.button("Delete this team", key="delete_team", icon=":material/delete:"):
        store.delete_team(uid, pick)
        notify("Team deleted")
        st.rerun()

st.header("Settings", anchor=False)
with st.expander("Change password"):
    with st.form("change_password", border=False, clear_on_submit=True):
        old = st.text_input("Current password", type="password", max_chars=128, autocomplete="current-password")
        new_pw = st.text_input("New password", type="password", max_chars=128, autocomplete="new-password")
        rep = st.text_input("Repeat new password", type="password", max_chars=128, autocomplete="new-password")
        change = st.form_submit_button("Change password", key="change_pw")
    if change:
        try:
            if new_pw != rep:
                raise AccountError("The two new passwords are different.")
            store.change_password(uid, old, new_pw, keep_token=current_token())
        except AccountError as err:
            st.error(str(err))
        else:
            st.success("Password changed. Other browsers are logged out.")
with st.expander("Delete account"):
    st.write("This deletes your account and every saved team. It cannot be undone.")
    with st.form("delete_account", border=False, clear_on_submit=True):
        confirm = st.text_input("Password", type="password", max_chars=128, autocomplete="current-password",
                                key="delete_pw")
        delete = st.form_submit_button("Delete my account", key="delete_account_btn")
    if delete:
        try:
            store.delete_account(uid, confirm)
        except AccountError as err:
            st.error(str(err))
        else:
            log_out()
            notify("Account deleted")
            st.rerun()
