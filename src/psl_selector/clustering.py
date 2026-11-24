"""K-means player-profile discovery (scikit-learn).

Clusters describe *playing style* (anchor, power hitter, strike bowler ...).
They are for analysis and the dashboard only; team-rule roles come from
metadata and are checked separately, as stated in the proposal.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from . import config as C

FEATURES = ["balls_per_match", "strike_rate", "boundary_pct", "bat_avg",
            "overs_per_match", "wickets_per_match", "economy", "dot_pct", "catches_per_match"]


def clean_features(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing rates and cap outliers at the 1.5 IQR fences of each feature."""
    X = df[FEATURES].copy()
    # Non-bowlers have no economy/dot%: give them neutral values so they cluster on batting.
    X["economy"] = X["economy"].fillna(X["economy"].median())
    X["dot_pct"] = X["dot_pct"].fillna(0)
    X["strike_rate"] = X["strike_rate"].fillna(X["strike_rate"].median())
    X = X.fillna(0)
    # Bowling rates from a handful of balls are noise: neutralize part-timers' economy.
    part_time = df["overs_per_match"] < 0.5
    X.loc[part_time, "economy"] = X["economy"].median()
    q1, q3 = X.quantile(0.25), X.quantile(0.75)
    fence = 1.5 * (q3 - q1)
    return X.clip(lower=q1 - fence, upper=q3 + fence, axis=1)


def feature_matrix(df: pd.DataFrame) -> np.ndarray:
    """Cleaned features, standardized to mean 0 and variance 1."""
    return StandardScaler().fit_transform(clean_features(df).values)


def compare_models(df: pd.DataFrame, k: int, seed: int = C.SEED) -> pd.DataFrame:
    """Compare K-means with Ward clustering, fitting on 70% of players and scoring the unseen 30%.

    Ward clustering cannot label new points, so both models label the unseen players
    by the nearest training-cluster centre, which keeps the comparison even.
    """
    X = clean_features(df).values
    train, test = train_test_split(np.arange(len(X)), test_size=0.3, random_state=seed)
    scaler = StandardScaler().fit(X[train])
    A, B = scaler.transform(X[train]), scaler.transform(X[test])
    models = {"K-means": KMeans(n_clusters=k, n_init=20, random_state=seed),
              "Ward hierarchical": AgglomerativeClustering(n_clusters=k, linkage="ward")}
    rows = []
    for name, model in models.items():
        labels = model.fit_predict(A)
        centres = np.array([A[labels == c].mean(axis=0) for c in range(k)])
        unseen = np.argmin(((B[:, None, :] - centres[None]) ** 2).sum(axis=2), axis=1)
        rows.append({"model": name, "k": k, "train_players": len(A), "test_players": len(B),
                     "silhouette_train": silhouette_score(A, labels),
                     "silhouette_test": silhouette_score(B, unseen)})
    return pd.DataFrame(rows).round(4)


class PlayerClusterer:
    """Choose k by silhouette score, fit K-means and name the resulting profiles."""

    def __init__(self, k_range=range(2, 9), seed: int = C.SEED):
        """Set the candidate k values and random seed."""
        self.k_range = k_range
        self.seed = seed
        self.silhouettes: dict[int, float] = {}
        self.k = None
        self.model = None

    def evaluate(self, X: np.ndarray) -> dict[int, float]:
        """Silhouette score for each candidate k."""
        for k in self.k_range:
            labels = KMeans(n_clusters=k, n_init=20, random_state=self.seed).fit_predict(X)
            self.silhouettes[k] = float(silhouette_score(X, labels))
        return self.silhouettes

    def fit_assign(self, df: pd.DataFrame, k: int | None = None) -> pd.DataFrame:
        """Cluster players and add cluster, PCA position and profile columns."""
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
        return df

    def silhouette_table(self) -> pd.DataFrame:
        """Silhouette scores as a table, marking the chosen k."""
        return pd.DataFrame({"k": list(self.silhouettes), "silhouette": list(self.silhouettes.values()),
                             "chosen": [kk == self.k for kk in self.silhouettes]})

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
