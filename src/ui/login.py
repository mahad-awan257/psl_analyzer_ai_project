"""The log in and create account screen, shown instead of any page until someone logs in."""
from __future__ import annotations

import streamlit as st

from psl_selector.accounts import MIN_PASSWORD, AccountError
from ui.components import page_head
from ui.session import accounts, log_in, notify


def login_screen() -> None:
    """Ask for a username and password, then open the home page."""
    page_head("Welcome to PSL Dugout", "Log in or create an account to continue.")
    _, middle, _ = st.columns([1, 1.6, 1])
    with middle:
        mode = st.segmented_control("Account", ["Log in", "Create account"], default="Log in", required=True,
                                    key="account_mode", label_visibility="collapsed", width="stretch")
        new = mode == "Create account"
        with st.form("create" if new else "login"):
            name = st.text_input("Username", key=f"name_{mode}", max_chars=24, autocomplete="username")
            password = st.text_input("Password", key=f"pw_{mode}", type="password", max_chars=128,
                                     autocomplete="new-password" if new else "current-password",
                                     help=f"At least {MIN_PASSWORD} characters." if new else None)
            again = st.text_input("Repeat password", key="pw_again", type="password", max_chars=128,
                                  autocomplete="new-password") if new else password
            stay = st.checkbox("Stay logged in for 30 days", value=True, key="stay",
                               help="Turn this off on a shared computer.")
            go = st.form_submit_button(mode, type="primary", width="stretch", key="submit_account")
        if go:
            try:
                if new and password != again:
                    raise AccountError("The two passwords are different.")
                store = accounts()
                user_id = store.create(name, password) if new else store.login(name, password)
                log_in(user_id, stay)
            except AccountError as err:
                st.error(str(err))
            else:
                notify("Account created" if new else "Logged in")
                st.switch_page("app_pages/home.py")
        st.caption("Accounts stay on this computer. There is no password reset, so choose one you will remember.")
