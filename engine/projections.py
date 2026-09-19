"""Blend multiple seasons into a per-game projection, then apply manual overrides.

Seasons CSVs (from data/fetch_stats.py) share the schema:
  PLAYER, PLAYER_ID, TEAM, POS, SEASON, GP, MIN, PTS, FG3M, REB, AST, STL, BLK,
  TOV, FGM, FGA, FTM, FTA

Overrides CSV (data/overrides.csv) lets you hand-edit for offseason changes:
  PLAYER, MIN_MULT (scale all counting stats), GP, POS, TEAM, NOTE
"""
import numpy as np
import pandas as pd
import config as C

RATE_COLS = ["PTS", "FG3M", "REB", "AST", "STL", "BLK", "TOV", "FGM", "FGA", "FTM", "FTA"]


def blend_seasons(seasons: list[pd.DataFrame]) -> pd.DataFrame:
    """seasons: most recent first. Per-36 rates blended, then scaled to blended minutes.

    Rookies / players with one season just get that season. Games-played regression:
    a season with fewer than MIN_GP_FOR_FULL_WEIGHT games is weighted down proportionally.
    """
    frames = []
    for i, s in enumerate(seasons):
        s = s.copy()
        w = C.SEASON_WEIGHTS[i] if i < len(C.SEASON_WEIGHTS) else 0.0
        s["_w"] = w * np.clip(s["GP"] / C.MIN_GP_FOR_FULL_WEIGHT, 0.25, 1.0)
        for col in RATE_COLS:
            s[f"_p36_{col}"] = s[col] / s["MIN"].replace(0, np.nan) * 36
        frames.append(s)
    all_ = pd.concat(frames, ignore_index=True)

    def agg(g):
        w = g["_w"].values
        wsum = w.sum()
        row = {"PLAYER": g["PLAYER"].iloc[0], "PLAYER_ID": g.name,
               "TEAM": g["TEAM"].iloc[0], "POS": g["POS"].iloc[0],
               "PRIOR_RANK": g["PRIOR_RANK"].dropna().iloc[0] if "PRIOR_RANK" in g and g["PRIOR_RANK"].notna().any() else np.nan,
               "MIN": np.average(g["MIN"], weights=w),
               "GP": np.average(g["GP"], weights=w), "_wsum": wsum}
        for col in RATE_COLS:
            p36 = np.nan_to_num(g[f"_p36_{col}"].values)
            row[col] = np.average(p36, weights=w) * row["MIN"] / 36
        return pd.Series(row)

    proj = all_.groupby("PLAYER_ID", sort=False).apply(agg, include_groups=False).reset_index(drop=True)
    return proj.drop(columns=["_wsum"])


def apply_overrides(proj: pd.DataFrame, overrides: pd.DataFrame | None) -> pd.DataFrame:
    if overrides is None or overrides.empty:
        return proj
    proj = proj.copy()
    ov = overrides.set_index("PLAYER")
    for name, r in ov.iterrows():
        m = proj["PLAYER"] == name
        if not m.any():
            continue
        mult = float(r.get("MIN_MULT", 1.0) or 1.0)
        if mult != 1.0:
            proj.loc[m, RATE_COLS + ["MIN"]] *= mult
        if pd.notna(r.get("GP")):
            proj.loc[m, "GP"] = float(r["GP"])
        if isinstance(r.get("POS"), str) and r["POS"]:
            proj.loc[m, "POS"] = r["POS"]
        if isinstance(r.get("TEAM"), str) and r["TEAM"]:
            proj.loc[m, "TEAM"] = r["TEAM"]
    return proj


def mark_no_stats(proj: pd.DataFrame, flags: pd.DataFrame | None) -> pd.DataFrame:
    """Players with no 2025-26 stats keep empty stat lines. data/no_stats.csv says which are
    returning players who missed the season (STATUS=INJ) and which have no NBA record at all (blank).
    Nothing is invented for them."""
    proj = proj.copy()
    proj["NO_STATS"] = proj["GP"].fillna(0) <= 0
    proj["STATUS"] = ""
    if flags is not None and not flags.empty:
        m = flags.set_index("PLAYER")["STATUS"].fillna("")
        known = proj["PLAYER"].map(m)
        proj.loc[known.notna(), "STATUS"] = known[known.notna()]
        proj.loc[proj["PLAYER"].isin(flags["PLAYER"]), "NO_STATS"] = True
    return proj


def load_projection(data_dir="data") -> pd.DataFrame:
    """Load season CSVs (season_*.csv, newest first) and overrides if present."""
    import glob, os
    files = sorted(glob.glob(os.path.join(data_dir, "season_*.csv")), reverse=True)
    if not files:
        raise FileNotFoundError("No data/season_*.csv found. Run data/fetch_stats.py or use sample data.")
    seasons = [pd.read_csv(f) for f in files[:3]]
    proj = blend_seasons(seasons)
    ns_path = os.path.join(data_dir, "no_stats.csv")
    ns = pd.read_csv(ns_path) if os.path.exists(ns_path) else None
    proj = mark_no_stats(proj, ns)
    ov_path = os.path.join(data_dir, "overrides.csv")
    ov = pd.read_csv(ov_path) if os.path.exists(ov_path) else None
    return apply_overrides(proj, ov)


def load_seasons(data_dir="data") -> list[pd.DataFrame]:
    """Raw season CSVs, newest first."""
    import glob, os
    files = sorted(glob.glob(os.path.join(data_dir, "season_*.csv")), reverse=True)
    return [pd.read_csv(f) for f in files[:3]]


STAT_COLS = ["GP", "MIN", "PTS", "FG3M", "REB", "AST", "STL", "BLK", "TOV", "FGA", "FTA"]


def with_pcts(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["FG_PCT"] = (out["FGM"] / out["FGA"].replace(0, np.nan)).fillna(0)
    out["FT_PCT"] = (out["FTM"] / out["FTA"].replace(0, np.nan)).fillna(0)
    return out


def season_totals(df: pd.DataFrame) -> pd.DataFrame:
    """Per-game season file -> season totals (per-game x GP), percentages kept."""
    out = with_pcts(df)
    for c in ["MIN", "PTS", "FG3M", "REB", "AST", "STL", "BLK", "TOV", "FGM", "FGA", "FTM", "FTA"]:
        out[c] = out[c] * out["GP"]
    return out


def multi_season_average(seasons: list[pd.DataFrame]) -> pd.DataFrame:
    """Straight games-weighted per-game average across the seasons provided."""
    tot = pd.concat([season_totals(s) for s in seasons])
    g = tot.groupby("PLAYER_ID")
    agg = g[["GP", "MIN", "PTS", "FG3M", "REB", "AST", "STL", "BLK", "TOV", "FGM", "FGA", "FTM", "FTA"]].sum()
    for c in ["MIN", "PTS", "FG3M", "REB", "AST", "STL", "BLK", "TOV", "FGM", "FGA", "FTM", "FTA"]:
        agg[c] = agg[c] / agg["GP"].replace(0, np.nan)
    agg["GP"] = agg["GP"] / len(seasons)
    first = pd.concat(seasons).drop_duplicates("PLAYER_ID").set_index("PLAYER_ID")[["PLAYER", "TEAM", "POS"]]
    return with_pcts(agg.join(first).reset_index())


def load_yahoo_projection(data_dir="data") -> pd.DataFrame | None:
    """Yahoo's own projected per-game stats, if data/yahoo_projections.csv exists.

    Expected columns: PLAYER, GP, MIN, FGM, FGA, FTM, FTA, FG3M, PTS, REB, AST, STL, BLK, TOV
    (FG_PCT / FT_PCT are accepted instead of made/attempted and converted).
    """
    import os
    path = os.path.join(data_dir, "yahoo_projections.csv")
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    df.columns = [c.strip().upper() for c in df.columns]
    df = df.rename(columns={"3PTM": "FG3M", "3PM": "FG3M", "ST": "STL", "TO": "TOV", "MPG": "MIN",
                            "FG%": "FG_PCT", "FT%": "FT_PCT", "NAME": "PLAYER"})
    for made, att, pct in [("FGM", "FGA", "FG_PCT"), ("FTM", "FTA", "FT_PCT")]:
        if made not in df.columns and pct in df.columns and att in df.columns:
            df[made] = pd.to_numeric(df[att], errors="coerce") * pd.to_numeric(df[pct], errors="coerce")
    need = ["GP", "MIN", "PTS", "FG3M", "REB", "AST", "STL", "BLK", "TOV", "FGM", "FGA", "FTM", "FTA"]
    for c in need:
        df[c] = pd.to_numeric(df.get(c), errors="coerce")
    # Yahoo's projection view reports season totals; convert to per game when it looks that way
    if df["PTS"].median() > 200:
        gp = df["GP"].replace(0, np.nan)
        for c in ["PTS", "FG3M", "REB", "AST", "STL", "BLK", "TOV", "FGM", "FGA", "FTM", "FTA"]:
            df[c] = df[c] / gp
    return df[["PLAYER"] + need].dropna(subset=["PLAYER"])


def _mkey(n):
    import re, unicodedata
    n = unicodedata.normalize("NFKD", str(n)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", n.lower())


def merge_yahoo_projection(proj: pd.DataFrame, yp: pd.DataFrame | None) -> pd.DataFrame:
    """Replace the derived projection with Yahoo's where Yahoo has a line. Players Yahoo
    doesn't cover keep the derived numbers, flagged in PROJ_SOURCE."""
    out = proj.copy()
    out["PROJ_SOURCE"] = "derived"
    if yp is None or yp.empty:
        return out
    cols = ["PTS", "FG3M", "REB", "AST", "STL", "BLK", "TOV", "FGM", "FGA", "FTM", "FTA"]
    m = yp.copy()
    m["_k"] = m["PLAYER"].map(_mkey)
    m = m.drop_duplicates("_k").set_index("_k")
    keys = out["PLAYER"].map(_mkey)
    hit = keys.isin(m.index)
    for c in cols + ["GP"]:
        out.loc[hit, c] = keys[hit].map(m[c]).values
    # Yahoo doesn't publish projected minutes, so keep the tool's own minute projection for context
    if "MIN_WHEN_PLAYING" in out.columns:
        out.loc[hit, "MIN"] = out.loc[hit, "MIN_WHEN_PLAYING"]
    out.loc[hit, "PROJ_GP"] = out.loc[hit, "GP"]
    out.loc[hit, "PROJ_SOURCE"] = "yahoo"
    out.loc[hit, "NO_STATS"] = False        # Yahoo projects rookies too
    return out
