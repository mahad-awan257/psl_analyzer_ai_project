"""Player value and simulated credits.

value  : season-weighted fantasy points per match, shrunk toward the role mean
         (players with few matches are pulled toward average), then z-scored
         *within role* and mapped to 50 + 15*z, clipped to [5, 100].
         Role-normalization means a keeper is compared with keepers, a bowler
         with bowlers, so the team utility is not biased toward one role.
credits: simulated cost from the overall percentile of raw weighted points per
         match (role-agnostic "market reputation"), mapped linearly onto
         [CREDIT_MIN, CREDIT_MAX] and rounded to 0.5. Because cost and value
         are measured differently, value-per-credit varies between players
         and the budget creates real trade-offs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C


def score_players(df: pd.DataFrame, k: float = C.SHRINKAGE_MATCHES) -> pd.DataFrame:
    df = df.copy()
    n = df["weight_sum"]
    role_mean = df.groupby("role")["weighted_ppm"].transform("mean")
    df["shrunk_ppm"] = (n * df["weighted_ppm"] + k * role_mean) / (n + k)
    grp = df.groupby("role")["shrunk_ppm"]
    std = grp.transform("std").replace(0, 1).fillna(1)
    z = (df["shrunk_ppm"] - grp.transform("mean")) / std
    df["value"] = (50 + 15 * z).clip(5, 100).round(2)
    pct = df["weighted_ppm"].rank(pct=True)
    raw = C.CREDIT_MIN + (C.CREDIT_MAX - C.CREDIT_MIN) * pct
    df["credits"] = (np.round(raw * 2) / 2).clip(C.CREDIT_MIN, C.CREDIT_MAX)
    return df
