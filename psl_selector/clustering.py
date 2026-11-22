"""K-means player-profile discovery (scikit-learn).

Clusters describe *playing style* (anchor, power hitter, strike bowler ...).
They are for analysis and the dashboard only; team-rule roles come from
metadata and are checked separately, as stated in the proposal.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from . import config as C

FEATURES = ["balls_per_match", "strike_rate", "boundary_pct", "bat_avg",
            "overs_per_match", "wickets_per_match", "economy", "dot_pct", "catches_per_match"]


def feature_matrix(df: pd.DataFrame) -> np.ndarray:
    X = df[FEATURES].copy()
    # Non-bowlers have no economy/dot%: give them neutral values so they cluster on batting.
    X["economy"] = X["economy"].fillna(X["economy"].median())
    X["dot_pct"] = X["dot_pct"].fillna(0)
    X["strike_rate"] = X["strike_rate"].fillna(X["strike_rate"].median())
    X = X.fillna(0)
    # Bowling rates from a handful of balls are noise: neutralize part-timers' economy.
    part_time = df["overs_per_match"] < 0.5
    X.loc[part_time, "economy"] = X["economy"].median()
    return StandardScaler().fit_transform(X.values)


class PlayerClusterer:
    def __init__(self, k_range=range(2, 9), seed: int = C.SEED):
        self.k_range = k_range
        self.seed = seed
        self.silhouettes: dict[int, float] = {}
        self.k = None
        self.model = None

    def evaluate(self, X: np.ndarray) -> dict[int, float]:
        for k in self.k_range:
            labels = KMeans(n_clusters=k, n_init=20, random_state=self.seed).fit_predict(X)
            self.silhouettes[k] = float(silhouette_score(X, labels))
        return self.silhouettes

    def fit_assign(self, df: pd.DataFrame, k: int | None = None) -> pd.DataFrame:
        X = feature_matrix(df)
        self.evaluate(X)
        # k=2 is a trivial batter/bowler split; choose the best k >= 3.
        candidates = {kk: s for kk, s in self.silhouettes.items() if kk >= 3}
        self.k = k or max(candidates, key=candidates.get)
        self.model = KMeans(n_clusters=self.k, n_init=20, random_state=self.seed).fit(X)
        df = df.copy()
        df["cluster"] = self.model.labels_
        pcs = PCA(n_components=2, random_state=self.seed).fit_transform(X)
        df["pc1"], df["pc2"] = pcs[:, 0], pcs[:, 1]
        df["profile"] = df["cluster"].map(self.label_clusters(df))
        pd.DataFrame({"k": list(self.silhouettes), "silhouette": list(self.silhouettes.values()),
                      "chosen": [kk == self.k for kk in self.silhouettes]}) \
            .to_csv(C.PROCESSED_DIR / "silhouette_scores.csv", index=False)
        return df

    @staticmethod
    def label_clusters(df: pd.DataFrame) -> dict[int, str]:
        """Human-readable names from cluster means (z-scored against all players)."""
        z = (df[FEATURES] - df[FEATURES].mean()) / df[FEATURES].std()
        means = z.groupby(df["cluster"]).mean()
        names = {}
        for c, m in means.iterrows():
            if m.overs_per_match > 0.8 and m.balls_per_match < -0.5:
                name = "Strike bowler" if m.wickets_per_match > -m.economy else "Economical bowler"
            elif m.overs_per_match > 0.2:
                name = "Batting all-rounder" if m.balls_per_match > 0.3 else "Bowling all-rounder / lower-order hitter"
            elif m.balls_per_match > 0.3:
                name = "Aggressive top-order" if m.strike_rate > 0.5 else "Top-order batter"
            elif m.strike_rate > 0.2 or m.boundary_pct > 0.2:
                name = "Finisher / power hitter"
            else:
                name = "Middle-order batter"
            names[c] = name
        # Make duplicates unique.
        seen = {}
        for c in sorted(names):
            n = names[c]
            seen[n] = seen.get(n, 0) + 1
            if seen[n] > 1:
                names[c] = f"{n} ({seen[n]})"
        return names
