"""The info icon at the bottom right of each page. Edit the text here."""
from __future__ import annotations

from html import escape

import streamlit as st

# Page title: (what the page shows, how it works)
PAGE_INFO = {
    "Home": ("The best team for 100 credits, the top players in each role, and how often each method finds the best team.", [
        "Backtracking picks the team shown on the field.",
        "Scores compare players within the same role. 50 is average.",
        "Percentages count only tests where a valid team exists.",
    ]),
    "Build XI": ("Pick your own team of eleven.", [
        "Set the budget and rules, choose one or more methods, then press Pick team.",
        "Backtracking proves the best team, Genetic evolves one, and Greedy takes the best value per credit.",
        "With two or more methods you can compare their teams.",
    ]),
    "Players": ("Records of every player you can select.", [
        "Search or filter, and click a column heading to sort.",
        "Value comes from fantasy points per match, with recent seasons counting more.",
        "Hover over a chart point to see the player.",
    ]),
    "Seasons": ("The best players of each season and how scoring has changed.", [
        "Pick a season to see its leaders.",
        "Strike rate and economy skip players with too few balls.",
        "Findings are worked out from the match data.",
    ]),
    "Styles": ("Groups of players who bat and bowl in a similar way.", [
        "K-means groups players using nine batting, bowling and fielding statistics.",
        "Players close together on the map have similar records.",
        "A higher silhouette score means clearer groups.",
    ]),
    "Results": ("How the three methods compare on 20 tests.", [
        "Each test has its own set of players and budget, and some have no valid team.",
        "Average gap is how far a team scores below the best one.",
        "Simple bound is backtracking without the budget-aware shortcut.",
    ]),
    "Log in": ("Log in or create an account to use the site.", [
        "Accounts are stored only on this computer.",
        "Passwords are kept as salted hashes, never as text.",
        "Stay logged in keeps you signed in on this browser for 30 days.",
    ]),
    "Account": ("Your saved teams and account settings.", [
        "Open this page from My teams on Home or Build XI.",
        "Save a team from Build XI and it appears here.",
        "Changing your password logs out your other browsers.",
    ]),
    "About": ("The group, the team rules and the data.", [
        "The rules listed are the defaults. You can change them in Build XI.",
        "Player credits are simulated, not official prices.",
    ]),
}

CSS = """
<style>
/* Take the icon out of the page flow, wrapper included, so it adds no gap under the navbar. */
[data-testid="stLayoutWrapper"]:has(> .st-key-page_info), .st-key-page_info,
[data-testid="stLayoutWrapper"]:has(> .st-key-cookie_sync), .st-key-cookie_sync { position: absolute; width: 0; height: 0; }
.pageinfo { position: fixed; right: 1.4rem; bottom: 1.4rem; z-index: 900; }
.pageinfo button { width: 3.2rem; height: 3.2rem; border-radius: 50%; border: 3px solid #fff; background: #14743F; color: #fff;
  font: 800 1.5rem/1 Archivo, Arial, sans-serif; cursor: help; box-shadow: 0 3px 12px rgba(12,59,33,.35); padding: 0; }
.pageinfo:hover button, .pageinfo button:focus { background: #0C3B21; }
.pageinfo button:focus-visible { outline: 3px solid #86E0A8; outline-offset: 2px; }
/* Padding below the panel keeps it open while the pointer moves from the icon to the text. */
.pageinfo .wrap { position: absolute; right: 0; bottom: 100%; padding-bottom: .7rem; visibility: hidden; opacity: 0; transition: opacity .12s; }
.pageinfo:hover .wrap, .pageinfo:focus-within .wrap { visibility: visible; opacity: 1; }
.pageinfo .panel { box-sizing: border-box; width: min(24rem, calc(100vw - 2.8rem)); max-height: calc(100vh - 11rem); overflow-y: auto;
  background: #fff; color: #12261A; border: 1px solid #C6DDCE; border-top: 6px solid #14743F; border-radius: 12px;
  padding: 1.1rem 1.3rem 1.2rem; box-shadow: 0 8px 28px rgba(12,59,33,.25); font-size: 1.02rem; line-height: 1.5; }
.pageinfo .name { font-size: 1.25rem; font-weight: 800; margin: 0 0 .3rem; }
.pageinfo .how { font-weight: 700; color: #14743F; margin: .8rem 0 .2rem; }
.pageinfo p { margin: 0; }
.pageinfo ul { margin: 0; padding-left: 1.15rem; }
.pageinfo li { margin: .25rem 0; font-size: 1.02rem; }
@media (prefers-reduced-motion: reduce) { .pageinfo .wrap { transition: none; } }
</style>
"""


def page_info(title: str) -> None:
    """Draw the info icon for a page."""
    if title not in PAGE_INFO:
        return
    what, how = PAGE_INFO[title]
    steps = "".join(f"<li>{escape(s)}</li>" for s in how)
    with st.container(key="page_info"):
        st.html(f'{CSS}<div class="pageinfo"><button type="button" aria-label="About this page" aria-describedby="pageinfo-text">i</button>'
                f'<div class="wrap"><div class="panel" role="tooltip" id="pageinfo-text"><p class="name">{escape(title)}</p>'
                f'<p>{escape(what)}</p><p class="how">How it works</p><ul>{steps}</ul></div></div></div>')
