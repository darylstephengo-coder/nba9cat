"""Nine-category z-score value engine with punt support.

Input DataFrame needs per-game columns:
  PLAYER, POS (e.g. "PG,SG"), GP, MIN, PTS, FG3M, REB, AST, STL, BLK, TOV,
  FGM, FGA, FTM, FTA
"""
import numpy as np
import pandas as pd
import config as C


def _pct_impact(df: pd.DataFrame, pool: pd.DataFrame, made: str, att: str) -> pd.Series:
    """Volume-weighted percentage impact: (player% - pool%) * attempts."""
    pool_pct = pool[made].sum() / max(pool[att].sum(), 1e-9)
    pct = df[made] / df[att].replace(0, np.nan)
    return ((pct - pool_pct) * df[att]).fillna(0)


def _z(series: pd.Series, pool_series: pd.Series) -> pd.Series:
    mu, sd = pool_series.mean(), pool_series.std(ddof=0)
    if sd == 0 or np.isnan(sd):
        return pd.Series(0.0, index=series.index)
    return (series - mu) / sd


def compute_values(df: pd.DataFrame, punts=None, pool_size: int = None,
                   tov_weight: float = C.TOV_WEIGHT, iterations: int = 2,
                   avail_weight: float = 0.5) -> pd.DataFrame:
    """Return df with z_<cat> columns, TOTAL (all nine cats), and VALUE (punt-adjusted).

    The reference pool is the top `pool_size` players by value, found iteratively
    so the baseline reflects players who actually get rostered in a 16-team league.
    """
    punts = set(punts or [])
    pool_size = pool_size or C.POOL_SIZE
    out = df.copy()

    pool = out.sort_values(["MIN", "GP"], ascending=False).head(pool_size)
    for _ in range(iterations):
        for cat in C.COUNTING_CATS:
            out[f"z_{cat}"] = _z(out[cat], pool[cat])
            if cat in C.NEGATIVE_CATS:
                out[f"z_{cat}"] *= -1
        for cat, (made, att) in C.PCT_CATS.items():
            imp_all = _pct_impact(out, pool, made, att)
            imp_pool = _pct_impact(pool, pool, made, att)
            out[f"z_{cat}"] = _z(imp_all, imp_pool)

        out["z_TOV"] *= tov_weight
        zcols = [f"z_{c}" for c in C.ALL_CATS]
        out["TOTAL"] = out[zcols].sum(axis=1)
        pool = out.sort_values("TOTAL", ascending=False).head(pool_size)

    keep = [f"z_{c}" for c in C.ALL_CATS if c not in punts]
    out["VALUE"] = out[keep].sum(axis=1)
    if "PROJ_GP" in out.columns:            # availability-weighted value for draft decisions
        out["AVAIL_VALUE"] = out["VALUE"] * (out["PROJ_GP"] / 82) ** avail_weight
    else:
        out["AVAIL_VALUE"] = out["VALUE"]
    out["RANK"] = out["VALUE"].rank(ascending=False, method="first").astype(int)
    return out.sort_values("VALUE", ascending=False)


def category_profile(roster: pd.DataFrame) -> pd.Series:
    """Sum of z-scores per category for a roster (what your team is strong/weak in)."""
    if roster.empty:
        return pd.Series({c: 0.0 for c in C.ALL_CATS})
    return pd.Series({c: roster[f"z_{c}"].sum() for c in C.ALL_CATS})
