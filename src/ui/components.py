"""Site-wide styling, the field view of a team, and shared chart settings."""
from __future__ import annotations

from html import escape

import altair as alt
import pandas as pd
import streamlit as st

from psl_selector import config as C
from psl_selector.player import Player

ROLE_ORDER = ["BAT", "AR", "BOWL", "WK"]
ROLE_COLORS = ["#2a78d6", "#eb6834", "#1baa7a", "#4a3aa7"]
ROLE_LABELS = [C.ROLE_NAMES[r] for r in ROLE_ORDER]

GREEN, GREEN_DARK = "#14743F", "#0C3B21"

CSS = """
<style>
/* Navigation bar */
[data-testid="stHeader"] { background: #0C3B21; }
[data-testid="stTopNavLink"] { background: transparent !important; padding: .45rem .9rem; }
[data-testid="stTopNavLink"] p, [data-testid="stTopNavLink"] span { color: #fff !important; font-size: 1.02rem; font-weight: 500; }
[data-testid="stTopNavLink"]:hover { background: #17573A !important; }
[data-testid="stTopNavLink"][aria-current="page"] { background: #86E0A8 !important; }
[data-testid="stTopNavLink"][aria-current="page"] p, [data-testid="stTopNavLink"][aria-current="page"] span { color: #0C3B21 !important; font-weight: 700; }
[data-testid="stExpandSidebarButton"] span { color: #fff; }

/* Log out button at the right of the navigation bar */
[data-testid="stLayoutWrapper"]:has(> .st-key-logout_bar), .st-key-logout_bar { position: absolute; width: 0; height: 0; }
.st-key-logout { position: fixed; top: .62rem; right: 1.2rem; z-index: 999991; width: auto; }
.st-key-logout button { background: transparent; border: 1.5px solid #86E0A8; min-height: 2.4rem; padding: .2rem 1rem; }
.st-key-logout button p { color: #fff; font-size: 1.02rem; font-weight: 600; white-space: nowrap; }
.st-key-logout button:hover, .st-key-logout button:focus-visible { background: #86E0A8; }
.st-key-logout button:hover p, .st-key-logout button:focus-visible p { color: #0C3B21; }
[data-testid="stHeader"]:has(nav) { padding-right: 8.5rem; box-sizing: border-box; }

/* Page width and full-width green bands */
.st-key-site_main, .st-key-site_footer { max-width: 1180px; margin: 0 auto; }
.st-key-hero, .st-key-band, .st-key-site_footer, .st-key-page_head { clip-path: inset(0 -100vmax); }
.st-key-hero { background: #14532F; box-shadow: 0 0 0 100vmax #14532F; padding: 3.2rem 0 3.4rem; }
.st-key-page_head { background: #14532F; box-shadow: 0 0 0 100vmax #14532F; padding: 2rem 0 2.2rem; margin-bottom: 1.2rem; }
.st-key-band { background: #EAF5EE; box-shadow: 0 0 0 100vmax #EAF5EE; padding: 3rem 0 3.4rem; }
.st-key-site_footer { background: #0C3B21; box-shadow: 0 0 0 100vmax #0C3B21; padding: 1.7rem 0; margin-top: 4rem; }
.st-key-home_methods { padding-top: 3rem; }
.st-key-band { margin-top: -1rem; }
.st-key-hero h1, .st-key-page_head h1 { color: #fff; padding: 0; letter-spacing: -.02em; }
.st-key-hero h1 { font-size: clamp(2.6rem, 5vw, 4.2rem); line-height: 1.04; text-wrap: balance; }
.st-key-page_head p { color: #CDEBD8; font-size: 1.15rem; margin-top: .5rem; }
.st-key-site_footer p, .st-key-site_footer a { color: #CDEBD8 !important; opacity: 1; font-size: 1rem; }
.members { color: #fff; opacity: .72; font-size: 1.08rem; line-height: 1.6; margin: 1rem 0 .6rem; }
.st-key-cta_build button { background: #86E0A8; border-color: #86E0A8; padding: .7rem 1.5rem; }
.st-key-cta_build button p { color: #0C3B21; font-size: 1.12rem; font-weight: 700; }
.st-key-cta_build button:hover { background: #A5EBC0; border-color: #A5EBC0; }

/* The chart hover box is attached to the document body and outlives its chart. Without these rules it
   shows as loose text at the top of the next page. */
#vg-tooltip-element { position: fixed; }
#vg-tooltip-element:not(.visible) { display: none !important; }
body:not(:has([data-testid="stVegaLiteChart"])) #vg-tooltip-element { display: none !important; }

.st-key-cta_teams button { background: transparent; border: 2px solid #86E0A8; padding: .7rem 1.5rem; }
.st-key-cta_teams button p { color: #fff; font-size: 1.12rem; font-weight: 600; }
.st-key-cta_teams button:hover { background: #17573A; }

/* Cricket field */
.field { position: relative; background: #1F8A4C; border-radius: 12px; padding: 1.6rem .6rem 1.4rem; overflow: hidden; }
.field i { position: absolute; box-sizing: border-box; }
.field .oval { inset: -9% -7%; border-radius: 50%; background: #2AA05C; }
.field .ring { inset: 18% 14%; border-radius: 50%; border: 2px dashed rgba(255,255,255,.22); }
.field .row { position: relative; display: flex; justify-content: center; gap: .4rem; margin-bottom: 1.2rem; }
.field .row:last-child { margin-bottom: 0; }
.field .p { flex: 0 1 8rem; min-width: 0; text-align: center; }
.field .c { display: inline-flex; align-items: center; justify-content: center; width: 3.1rem; height: 3.1rem; border-radius: 50%;
  background: #fff; color: #0C3B21; font-weight: 800; font-size: 1.12rem; font-variant-numeric: tabular-nums; }
.field .c.os { background: #FFD34D; }
.field .n { display: block; width: fit-content; max-width: 100%; margin: .4rem auto 0; padding: .14rem .5rem; border-radius: 6px; background: #0C3B21; color: #fff;
  font-weight: 600; font-size: .9rem; line-height: 1.2; overflow-wrap: break-word; }
.key { font-size: 1rem; margin: .7rem 0 0; opacity: .8; }
.st-key-hero .key { color: #fff; }

/* Rankings and method results */
.ranks > div { padding: .55rem 0 .7rem; }
.ranks .t { display: flex; justify-content: space-between; gap: .75rem; font-size: 1.1rem; font-weight: 600; }
.ranks .t b { font-weight: 800; color: #14743F; font-variant-numeric: tabular-nums; }
.ranks .b { height: 8px; border-radius: 4px; background: #CFE6D7; margin-top: .4rem; }
.ranks .b span { display: block; height: 100%; border-radius: 4px; background: #1F8A4C; }
.method { background: #14532F; color: #fff; border-radius: 12px; padding: 1.6rem 1.7rem; height: 100%; }
.method h3 { margin: 0; padding: 0; font-size: 1.45rem; font-weight: 700; color: #fff; }
.method .big { font-size: 3.3rem; font-weight: 800; line-height: 1.1; color: #86E0A8; margin: .8rem 0 .1rem; }
.method p { margin: 0; font-size: 1.08rem; }
@media (max-width: 767px) {
  [data-testid="stHeaderLogo"] { height: 1.35rem !important; }
  .st-key-logout { right: .7rem; top: .75rem; }
  .st-key-logout button { padding: .1rem .7rem; min-height: 2.1rem; }
  .st-key-logout button p { font-size: .9rem; }
}
@media (max-width: 640px) {
  .st-key-hero { padding: 2rem 0; }
  .field .p { flex-basis: 5rem; }
  .field .c { width: 2.5rem; height: 2.5rem; font-size: .98rem; }
  .field { padding-left: .25rem; padding-right: .25rem; }
  .field .row { gap: .15rem; }
  .field .n { font-size: .62rem; padding: .12rem .16rem; overflow-wrap: normal; }
}
</style>
"""

OVAL = '<i class="oval"></i><i class="ring"></i>'


def page_head(title: str, sub: str = "") -> None:
    """Green page banner."""
    with st.container(key="page_head", gap="xsmall"):
        st.title(title, anchor=False)
        if sub:
            st.markdown(sub)


def field(team: list[Player]) -> None:
    """Draw a team on a cricket oval, one row per role."""
    rows = []
    for role in ["WK", "BAT", "AR", "BOWL"]:
        group = [p for p in team if p.role == role]
        # Rows longer than five are split so names stay readable.
        for i in range(0, len(group), 5):
            cells = "".join(
                f'<div class="p"><span class="c{" os" if p.overseas else ""}">{p.credits:g}</span>'
                f'<span class="n">{escape(p.name)}</span></div>' for p in group[i:i + 5])
            rows.append(f'<div class="row">{cells}</div>')
    st.html(f'<div class="field">{OVAL}{"".join(rows)}</div>'
            '<p class="key">Number: credits. Yellow: overseas player.</p>')


def ranking(df: pd.DataFrame, bars: bool = True, digits: int = 0) -> None:
    """Names with values, and bars when the values are out of 100."""
    items = "".join(f'<div><div class="t"><span>{escape(n)}</span><b>{v:.{digits}f}</b></div>'
                    + (f'<div class="b"><span style="width:{v:.0f}%"></span></div>' if bars else '') + '</div>'
                    for n, v in zip(df["name"], df["value"]))
    st.html(f'<div class="ranks">{items}</div>')


def method_card(name: str, big: str, text: str) -> None:
    """Card with one large figure."""
    st.html(f'<div class="method"><h3>{escape(name)}</h3><div class="big">{escape(big)}</div><p>{escape(text)}</p></div>')


def person_card(name: str, roll: str, work: str) -> None:
    """Card for a group member."""
    st.html(f'<div class="method"><h3>{escape(name)}</h3><p style="color:#86E0A8;margin:.4rem 0 .8rem">{escape(roll)}</p>'
            f'<p>{escape(work)}</p></div>')


def big_text(chart):
    """Readable axis and legend text on every chart."""
    return (chart.configure_axis(labelFontSize=14, titleFontSize=15, labelColor="#33453A", titleColor="#12261A",
                                 gridColor="#E1EDE5")
            .configure_legend(labelFontSize=15, labelColor="#12261A", symbolSize=110))


def role_scatter(df: pd.DataFrame, x: str, y: str, x_title: str, y_title: str, extra: list, alt_text: str) -> None:
    """Scatter chart coloured and shaped by role."""
    data = df.assign(role_name=df.role.map(C.ROLE_NAMES))
    present = [r for r in ROLE_LABELS if r in set(data.role_name)]
    colors = [ROLE_COLORS[ROLE_LABELS.index(r)] for r in present]
    shapes = [dict(zip(ROLE_LABELS, ["circle", "square", "triangle-up", "diamond"]))[r] for r in present]
    chart = alt.Chart(data).mark_point(size=90, filled=True, opacity=0.85).encode(
        x=alt.X(x, title=x_title, scale=alt.Scale(zero=False)),
        y=alt.Y(y, title=y_title, scale=alt.Scale(zero=False)),
        color=alt.Color("role_name:N", title=None, scale=alt.Scale(domain=present, range=colors),
                        legend=alt.Legend(orient="top")),
        shape=alt.Shape("role_name:N", title=None, scale=alt.Scale(domain=present, range=shapes)),
        tooltip=[alt.Tooltip("name", title="Player"), alt.Tooltip("role_name", title="Role"), *extra],
    ).properties(height=340)
    st.altair_chart(big_text(chart), width="stretch", alt=alt_text)


def with_origin(df: pd.DataFrame) -> pd.DataFrame:
    """Show the overseas flag as Local or Overseas."""
    return df.assign(overseas=df.overseas.map({True: "Overseas", False: "Local"}))


PLAYER_COLUMNS = {
    "name": "Player",
    "role": "Role", "team": "Last team", "matches": "Matches", "runs": "Runs", "wickets": "Wickets",
    "overseas": "Origin",
    "strike_rate": st.column_config.NumberColumn("Strike rate", format="%.1f"),
    "bat_avg": st.column_config.NumberColumn("Average", format="%.1f"),
    "economy": st.column_config.NumberColumn("Economy", format="%.2f"),
    "points_per_match": st.column_config.NumberColumn("Points / match", format="%.1f"),
    "value": st.column_config.NumberColumn("Value", format="%.1f"),
    "credits": st.column_config.NumberColumn("Credits", format="%.1f"),
    "profile": "Playing style",
}
