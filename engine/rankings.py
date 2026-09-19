"""Your own rankings, tiers, ADP, and notes, blended with the model.

data/my_rankings.csv columns:
  PLAYER   exact name as in the stats file
  MY_RANK  your overall rank (blank = use the model)
  TIER     optional tier number (1 = best)
  ADP      optional average draft position from Yahoo or any site, sharpens "likely gone"
  YAHOO_RANK  Yahoo preseason (O-Rank), filled by data/import_yahoo.py
  X_RANK   Yahoo X-Rank, read off the draft room (data/yahoo_xrank.csv)
  ADP_PREV ADP from the previous dated snapshot, for movement
  AVOID    True = do-not-draft; hidden from draft recommendations and the slot planner
  NOTE     anything: "hate the FT%", "target in round 6", injury worries
"""
import os
import pandas as pd

PATH = "data/my_rankings.csv"
COLS = ["PLAYER", "MY_RANK", "TIER", "ADP", "PCT_DRAFTED", "ADP_PREV", "YAHOO_RANK", "X_RANK", "AVOID", "NOTE"]


def load(path: str = PATH) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame(columns=COLS)
    df = pd.read_csv(path)
    for c in COLS:
        if c not in df.columns:
            df[c] = pd.NA
    for c in ["MY_RANK", "TIER", "ADP", "PCT_DRAFTED", "ADP_PREV", "YAHOO_RANK", "X_RANK"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["NOTE"] = df["NOTE"].fillna("").astype(str)
    df["AVOID"] = df["AVOID"].map(lambda v: str(v).strip().lower() in ("true", "1", "yes", "x")).astype(bool)
    return df[COLS].dropna(subset=["PLAYER"])


def save(df: pd.DataFrame, path: str = PATH) -> None:
    keep = df[COLS].copy()
    keep = keep[keep["PLAYER"].notna() & (keep["PLAYER"].astype(str).str.strip() != "")]
    keep["AVOID"] = keep["AVOID"].fillna(False).astype(bool)
    keep = keep[keep[["MY_RANK", "TIER", "ADP", "YAHOO_RANK", "X_RANK"]].notna().any(axis=1)
                | (keep["NOTE"].fillna("") != "") | keep["AVOID"]]
    keep.to_csv(path, index=False)


def blend(board: pd.DataFrame, mine: pd.DataFrame, trust: float, score_col: str = "VALUE") -> pd.DataFrame:
    """Add MY_RANK/TIER/ADP/NOTE and a BLEND_RANK column.

    BLEND_RANK = trust * MY_RANK + (1 - trust) * model rank, for players you ranked;
    unranked players keep the model rank. trust=1 means your order rules wherever you set one.
    """
    out = board.drop(columns=[c for c in COLS[1:] if c in board.columns])
    out = out.merge(mine, on="PLAYER", how="left")
    model_rank = out[score_col].rank(ascending=False, method="first")
    own = out["MY_RANK"]
    raw = (trust * own + (1 - trust) * model_rank).where(own.notna(), model_rank + 0.5)
    # +0.5 lets a player you ranked 12th go ahead of the model's unranked 12th
    out["BLEND_RANK"] = raw.rank(method="first").astype(int)
    out["NOTE"] = out["NOTE"].fillna("")
    out["AVOID"] = out["AVOID"].fillna(False).astype(bool)
    return out.sort_values("BLEND_RANK")


def set_avoid(mine: pd.DataFrame, player: str, avoid: bool) -> pd.DataFrame:
    mine = mine.copy()
    if player in set(mine["PLAYER"]):
        mine.loc[mine["PLAYER"] == player, "AVOID"] = avoid
    else:
        mine = pd.concat([mine, pd.DataFrame([{"PLAYER": player, "AVOID": avoid, "NOTE": ""}])], ignore_index=True)
    mine["AVOID"] = mine["AVOID"].fillna(False).astype(bool)
    return mine


def market_rank(board: pd.DataFrame) -> pd.Series:
    """Where the market puts a player: the average of Yahoo X-Rank and ADP, whichever exist."""
    parts = [board[c] for c in ("X_RANK", "ADP") if c in board.columns]
    if not parts:
        return pd.Series(250.0, index=board.index)
    return pd.concat(parts, axis=1).mean(axis=1, skipna=True)


def rank_with_no_stats(board: pd.DataFrame, inj_discount: float, rookie_discount: float) -> pd.DataFrame:
    """Produce MY_VALUE for every player.

    Players with 2025-26 stats are ranked by the model (AVAIL_VALUE).
    Players without stats can't be modelled, so they take the market's rank (X-Rank and ADP
    averaged) pushed down by a discount: bigger for rookies than for a veteran coming back
    from a lost season. BASIS says which route each player took.
    """
    out = board.copy()
    no_stats = out["NO_STATS"].fillna(False).astype(bool) if "NO_STATS" in out.columns \
        else pd.Series(False, index=out.index)
    status = out["STATUS"].fillna("") if "STATUS" in out.columns else pd.Series("", index=out.index)

    model = out.loc[~no_stats, "AVAIL_VALUE"].rank(ascending=False, method="first")
    key = pd.Series(index=out.index, dtype=float)
    key[~no_stats] = model

    mkt = market_rank(out).fillna(250.0)
    disc = pd.Series(rookie_discount, index=out.index)
    disc[status == "INJ"] = inj_discount
    key[no_stats] = mkt[no_stats] * (1 + disc[no_stats])

    out["BASIS"] = "stats"
    out.loc[no_stats & (status == "INJ"), "BASIS"] = "market − injury"
    out.loc[no_stats & (status != "INJ"), "BASIS"] = "market − rookie"
    out["MY_VALUE"] = key.rank(method="first").astype(int)
    return out
