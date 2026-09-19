"""Add/drop scoring: rest-of-season value + this-week schedule + team fit."""
import pandas as pd
import config as C
from engine.zscores import category_profile


def score_free_agents(board: pd.DataFrame, my_roster: pd.DataFrame, free_agents: list,
                      games_by_team: dict | None = None, week_weight: float = 0.3,
                      punts=None) -> pd.DataFrame:
    """Rank free agents for pickup. WEEK_BOOST rewards extra games this week.
    DROP_CANDIDATE shows the weakest player on my roster for comparison."""
    punts = set(punts or [])
    fa = board[board["PLAYER"].isin(free_agents)].copy()
    prof = category_profile(my_roster)
    live = [c for c in C.ALL_CATS if c not in punts]
    centered = prof[live] - prof[live].mean()
    need = (-centered).clip(lower=0)
    need = need / need.sum() if need.sum() > 0 else need
    fa["FIT"] = sum(fa[f"z_{c}"] * need[c] for c in live) * len(live)
    if games_by_team:
        g = fa["TEAM"].map(games_by_team).fillna(3.5)
        fa["GAMES_WK"] = g
        fa["WEEK_BOOST"] = (g - 3.5) * fa["VALUE"].clip(lower=0) * week_weight
    else:
        fa["GAMES_WK"], fa["WEEK_BOOST"] = 3.5, 0.0
    fa["PICKUP_SCORE"] = fa["VALUE"] + 0.3 * fa["FIT"] + fa["WEEK_BOOST"]
    worst = my_roster.sort_values("VALUE").head(3)[["PLAYER", "VALUE"]]
    fa.attrs["drop_candidates"] = worst
    cols = ["PLAYER", "TEAM", "POS", "PICKUP_SCORE", "VALUE", "FIT", "GAMES_WK", "WEEK_BOOST"]
    return fa.sort_values("PICKUP_SCORE", ascending=False)[cols].round(2)


def streaming_targets(board, taken: set, games_by_team: dict, min_games: int = 4, n: int = 20):
    """Best available players on teams with a heavy schedule this week."""
    fa = board[~board["PLAYER"].isin(taken)].copy()
    fa["GAMES_WK"] = fa["TEAM"].map(games_by_team).fillna(3)
    return fa[fa["GAMES_WK"] >= min_games].head(n)[["PLAYER", "TEAM", "POS", "VALUE", "GAMES_WK"]].round(2)
