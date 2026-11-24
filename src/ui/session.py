"""Who is logged in, and the cookie that keeps them logged in.

Every login has a random token. This tab keeps it in session state. With "Stay logged in" the
browser also keeps it in a cookie, so a refresh or a restart does not ask for the password again.
The cookie is set by JavaScript, so it is not HttpOnly. That is acceptable for a local app; a
public site should set it from the server over HTTPS.
"""
from __future__ import annotations

import json

import streamlit as st

from psl_selector.accounts import STAY_SECONDS, AccountStore

COOKIE = "psl_dugout_session"


@st.cache_resource
def accounts() -> AccountStore:
    """The local account database."""
    return AccountStore()


def current_token() -> str | None:
    """This tab's token, or the one in the browser's cookie."""
    if token := st.session_state.get("token"):
        return token
    # After a log out in this tab, the cookie read at page load must not log the user back in.
    return None if st.session_state.get("logged_out") else st.context.cookies.get(COOKIE)


def current_user() -> tuple[int, str] | None:
    """(id, username) of the logged-in user, or None. Re-checked on every run."""
    token = current_token()
    user = accounts().session_user(token)
    if user:
        st.session_state.token = token
    else:
        st.session_state.pop("token", None)
    return user


def log_in(user_id: int, stay: bool) -> None:
    """Start a session, replacing any session this browser already had."""
    accounts().end_session(st.context.cookies.get(COOKIE))
    st.session_state.token = accounts().start_session(user_id, stay)
    st.session_state.pop("logged_out", None)
    st.session_state.cookie_write = st.session_state.token if stay else ""


def log_out() -> None:
    """End this session, remove the cookie and clear this tab's data."""
    accounts().end_session(current_token())
    for key in list(st.session_state):
        del st.session_state[key]
    st.session_state.logged_out = True
    st.session_state.cookie_write = ""


def sync_cookie() -> None:
    """Send a pending cookie change to the browser. An empty token removes the cookie."""
    token = st.session_state.pop("cookie_write", None)
    if token is None:
        return
    age = STAY_SECONDS if token else 0
    with st.container(key="cookie_sync"):
        st.html(f"""<script>
            document.cookie = {json.dumps(f"{COOKIE}={token}; path=/; max-age={age}; SameSite=Strict")}
                + (location.protocol === "https:" ? "; Secure" : "");
        </script>""", unsafe_allow_javascript=True)


def notify(text: str) -> None:
    """Show a short message after the next rerun."""
    st.session_state.notice = text


def show_notice() -> None:
    """Show a message left by notify()."""
    if text := st.session_state.pop("notice", None):
        st.toast(text, icon=":material/check_circle:")
