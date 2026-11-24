"""Playing styles page (K-means)."""
import altair as alt
import streamlit as st

from psl_selector import config as C
from ui.components import GREEN, ROLE_COLORS, big_text, page_head
from ui.data import clustered, csv, players_df

df = players_df()
sil = csv(str(C.PROCESSED_DIR / "silhouette_scores.csv"))
best_k = int(sil[sil.chosen].k.iloc[0]) if sil is not None else 3

page_head("Playing styles", "Players grouped by how they bat and bowl, using K-means.")

# Four is the most groups the colour set keeps distinct for colour-blind readers.
k = st.segmented_control("Number of styles", [2, 3, 4], default=best_k, required=True, key="k")
prof = df if k == best_k else clustered(k)
styles = sorted(prof.profile.unique())

a, b = st.columns([1.7, 1], gap="large")
with a:
    st.subheader("Player map", anchor=False)
    scale = alt.Scale(domain=styles, range=ROLE_COLORS[:len(styles)])
    shapes = alt.Scale(domain=styles, range=["circle", "square", "triangle-up", "diamond"][:len(styles)])
    chart = alt.Chart(prof).mark_point(size=95, filled=True, opacity=0.85).encode(
        x=alt.X("pc1:Q", title="Component 1", axis=alt.Axis(labels=False, ticks=False)),
        y=alt.Y("pc2:Q", title="Component 2", axis=alt.Axis(labels=False, ticks=False)),
        color=alt.Color("profile:N", title=None, scale=scale, legend=alt.Legend(orient="top", columns=1, labelLimit=320)),
        shape=alt.Shape("profile:N", title=None, scale=shapes),
        tooltip=[alt.Tooltip("name", title="Player"), alt.Tooltip("profile", title="Style"),
                 alt.Tooltip("strike_rate:Q", title="Strike rate", format=".1f"),
                 alt.Tooltip("wickets", title="Wickets")],
    ).properties(height=430)
    st.altair_chart(big_text(chart), width="stretch", alt="Players placed by similarity and grouped by playing style")
with b:
    st.subheader("Group quality", anchor=False)
    if sil is not None:
        line = alt.Chart(sil).mark_line(point=alt.OverlayMarkDef(size=90, filled=True, color=GREEN), strokeWidth=3, color=GREEN).encode(
            x=alt.X("k:O", title="Number of styles", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("silhouette:Q", title="Silhouette score", scale=alt.Scale(domain=[0, 0.45])),
            tooltip=[alt.Tooltip("k", title="Styles"), alt.Tooltip("silhouette", title="Score", format=".3f")],
        ).properties(height=260)
        st.altair_chart(big_text(line), width="stretch", alt="Silhouette score falls as the number of styles grows")
        st.markdown(f"Higher is better. Two only splits batters from bowlers, so we use **{best_k}**.")

st.subheader("Average record by style", anchor=False)
names = {"balls_per_match": "Balls / match", "strike_rate": "Strike rate", "overs_per_match": "Overs / match",
         "wickets_per_match": "Wickets / match", "economy": "Economy"}
means = prof.groupby("profile")[list(names)].mean().round(1).rename(columns=names)
means.insert(0, "Players", prof.profile.value_counts())
st.dataframe(means.rename_axis("Style"), alt="Average statistics for each style")

chosen = st.selectbox("See players in a style", styles, key="style")
st.markdown(", ".join(prof[prof.profile == chosen].sort_values("name").name))
