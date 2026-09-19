"""Weekly head-to-head projection using games scheduled for each player's team."""
import pandas as pd
import config as C


def weekly_totals(roster: pd.DataFrame, games_by_team: dict, default_games: float = 3.5) -> pd.Series:
    g = roster["TEAM"].map(games_by_team).fillna(default_games)
    tot = {}
    for cat in C.COUNTING_CATS:
        tot[cat] = float((roster[cat] * g).sum())
    for cat, (made, att) in C.PCT_CATS.items():
        m, a = (roster[made] * g).sum(), (roster[att] * g).sum()
        tot[cat] = float(m / a) if a else 0.0
    tot["GAMES"] = float(g.sum())
    return pd.Series(tot)


def compare(my_roster, opp_roster, games_by_team, default_games=3.5) -> pd.DataFrame:
    a = weekly_totals(my_roster, games_by_team, default_games)
    b = weekly_totals(opp_roster, games_by_team, default_games)
    rows = []
    for cat in C.ALL_CATS:
        win = a[cat] < b[cat] if cat in C.NEGATIVE_CATS else a[cat] > b[cat]
        margin = (a[cat] - b[cat]) / max(abs(b[cat]), 1e-9)
        rows.append({"CAT": cat, "ME": round(a[cat], 3 if "PCT" in cat else 1),
                     "OPP": round(b[cat], 3 if "PCT" in cat else 1),
                     "WIN": bool(win), "MARGIN%": round(margin * 100, 1)})
    df = pd.DataFrame(rows)
    df.attrs["score"] = f"{int(df['WIN'].sum())}-{int((~df['WIN']).sum())}"
    df.attrs["games"] = (a["GAMES"], b["GAMES"])
    return df
