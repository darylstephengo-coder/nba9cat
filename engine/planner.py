"""Pre-draft slot planner: your pick numbers in a snake draft and who is likely available at each."""
import pandas as pd
import config as C


def my_picks(slot: int, rounds: int = None, teams: int = None) -> list[int]:
    rounds = rounds or C.ROSTER_SIZE
    teams = teams or C.TEAMS
    picks = []
    for r in range(1, rounds + 1):
        picks.append((r - 1) * teams + slot if r % 2 == 1 else r * teams - slot + 1)
    return picks


def market_position(board: pd.DataFrame) -> pd.Series:
    """Where the market takes a player: ADP if we have it, else Yahoo preseason rank, else model rank."""
    model = board["AVAIL_VALUE"].rank(ascending=False, method="first")
    proxy = board["ADP"] if "ADP" in board.columns else pd.Series(index=board.index, dtype=float)
    if "YAHOO_RANK" in board.columns:
        proxy = proxy.fillna(board["YAHOO_RANK"] * 1.05)      # rank tends to run slightly ahead of ADP
    return proxy.fillna(model)


def plan(board: pd.DataFrame, slot: int, n_per_pick: int = 6, reach: int = 6, window: int = 20) -> pd.DataFrame:
    """For each of your picks, the best-value players the market usually leaves there.

    A player is 'likely there' if their market position >= pick - reach (a small reach is normal),
    and 'in range' if it's <= pick + window (drafting them here isn't a wild reach either way).
    """
    b = board.copy()
    if "AVOID" in b.columns:
        b = b[~b["AVOID"].fillna(False).astype(bool)]
    b["MARKET"] = market_position(b)
    b["MODEL_RANK"] = b["AVAIL_VALUE"].rank(ascending=False, method="first").astype(int)
    rows = []
    for rnd, pick in enumerate(my_picks(slot), start=1):
        cands = b[(b["MARKET"] >= pick - reach) & (b["MARKET"] <= pick + window)]
        cands = cands.sort_values("AVAIL_VALUE", ascending=False).head(n_per_pick)
        for _, p in cands.iterrows():
            rows.append({"ROUND": rnd, "PICK": pick, "PLAYER": p["PLAYER"], "POS": p["POS"],
                         "MARKET": round(float(p["MARKET"]), 1), "MODEL_RANK": int(p["MODEL_RANK"]),
                         "VALUE": round(float(p["AVAIL_VALUE"]), 2),
                         "EDGE": int(round(p["MARKET"] - p["MODEL_RANK"])),
                         "SOURCE": p.get("SOURCE", "")})
    return pd.DataFrame(rows)
