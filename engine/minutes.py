"""Project each team's rotation so healthy-lineup minutes sum to 240 per game (48 min x 5 spots).

Per team:
  1. Rotation order = last season's minutes per game, blended toward the minutes implied by the
     player's Yahoo preseason rank when the sample is small (< 30 games), so a star who missed most
     of last year still projects as a starter and a 4-game fill-in doesn't.
  2. Scale those minutes so the team sums to 240, cap any player at `cap`, redistribute excess,
     and reduce players outside the top 11 to garbage-time minutes.
     -> MIN_WHEN_PLAYING (minutes on nights they play)
  3. Projected games: last season's GP regressed halfway toward 65 (nobody projects for 5 games
     or for 82). Override per player with GP in data/overrides.csv.
     -> PROJ_GP, and MIN_PROJ = MIN_WHEN_PLAYING x PROJ_GP / 82 (season-average share of the 240)
  4. Roles by rank: Starter (1-5), Rotation (6-9), Fringe (10-11), Out (rest).

Counting stats are then rescaled per-36 to MIN_WHEN_PLAYING, so a player moving into an open
rotation projects up and one joining a crowded team projects down.
"""
import numpy as np
import pandas as pd

TEAM_MINUTES = 240.0
GP_ANCHOR = 65.0
RATE_COLS = ["PTS", "FG3M", "REB", "AST", "STL", "BLK", "TOV", "FGM", "FGA", "FTM", "FTA"]


def _rank_minutes(rank):
    """Minutes a healthy player at this preseason rank typically gets."""
    if pd.isna(rank):
        return np.nan
    return 34 if rank <= 40 else 32 if rank <= 90 else 29 if rank <= 150 else 25 if rank <= 220 else \
        20 if rank <= 300 else 14 if rank <= 380 else 8


def healthy_minutes(df: pd.DataFrame, min_gp: float = 30) -> pd.Series:
    """Last season's minutes per game, but for small samples blend toward what the player's
    preseason rank implies, so 15 games of a returning star (or 4 games of a fringe guy)
    don't set the rotation order."""
    w = (df["GP"] / min_gp).clip(0, 1)
    prior = df["PRIOR_RANK"].map(_rank_minutes) if "PRIOR_RANK" in df.columns else pd.Series(np.nan, index=df.index)
    fallback = df["MIN"] * (df["GP"] / 25).clip(0.15, 1)      # no prior available: shrink small samples
    prior = prior.fillna(fallback)
    return df["MIN"] * w + prior * (1 - w)


def _distribute(mins: pd.Series, cap: float, total: float) -> pd.Series:
    """Fit a team's minutes to 240 without stealing from the starters.

    Yahoo lists 15-18 players per team, many with minutes earned elsewhere, so raw minutes
    usually add up to well over 240. Starters keep what they actually played (up to the cap);
    the squeeze falls on the bench. If a team is short of 240, the rotation scales up instead.
    """
    m = mins.clip(lower=0).astype(float)
    if m.sum() == 0:
        return m
    order = m.sort_values(ascending=False).index
    out = pd.Series(0.0, index=m.index)

    starters = order[:5]
    out[starters] = m[starters].clip(upper=cap)
    left = total - out[starters].sum()

    rest = order[5:]
    if len(rest) and left > 0:
        want = m[rest].clip(upper=cap)
        if want.sum() <= left:                       # room to spare: give them their minutes,
            out[rest] = want                          # then scale the rotation up to fill 240
            short = left - want.sum()
            if short > 0:
                rot = order[:11]
                room = (cap - out[rot]).clip(lower=0)
                if room.sum() > 0:
                    out[rot] += short * room / room.sum()
        else:                                         # too many minutes: bench absorbs the cut
            out[rest] = want * left / want.sum()
    return out


def project_team_minutes(proj: pd.DataFrame, cap: float = 36.0, availability: bool = True) -> pd.DataFrame:
    out = proj.copy()
    out["PROJ_GP"] = (0.5 * out["GP"] + 0.5 * GP_ANCHOR).clip(15, 80) if availability else 80.0
    out["MIN_WHEN_PLAYING"] = 0.0
    out["_healthy"] = healthy_minutes(out)
    if "NO_STATS" in out.columns:
        out.loc[out["NO_STATS"], "_healthy"] = 0.0
    for team, g in out.groupby("TEAM"):
        healthy = g["_healthy"].copy()
        rank = healthy.rank(ascending=False, method="first")
        healthy[(rank > 11) & (rank <= 13)] *= 0.2      # 12th/13th man: spot minutes
        healthy[rank > 13] *= 0.05                       # everyone else: garbage time only
        out.loc[g.index, "MIN_WHEN_PLAYING"] = _distribute(healthy, cap, TEAM_MINUTES)
    out = out.drop(columns=["_healthy"])
    out["MIN_PROJ"] = out["MIN_WHEN_PLAYING"] * out["PROJ_GP"] / 82
    out["ROT_RANK"] = out.groupby("TEAM")["MIN_WHEN_PLAYING"].rank(ascending=False, method="first").astype(int)
    out["ROLE"] = pd.cut(out["ROT_RANK"], [0, 5, 9, 11, 99],
                         labels=["Starter", "Rotation", "Fringe", "Out"]).astype(str)
    out["MIN_CHANGE"] = out["MIN_WHEN_PLAYING"] - out["MIN"]
    return out


def apply_minutes(proj_with_minutes: pd.DataFrame) -> pd.DataFrame:
    out = proj_with_minutes.copy()
    ratio = (out["MIN_WHEN_PLAYING"] / out["MIN"].replace(0, np.nan)).fillna(1.0).clip(0.4, 1.6)
    for c in RATE_COLS:
        out[c] = out[c] * ratio
    out["MIN_ORIG"] = out["MIN"]
    out["MIN"] = out["MIN_WHEN_PLAYING"]
    return out


def depth_chart(proj_with_minutes: pd.DataFrame, team: str) -> pd.DataFrame:
    g = proj_with_minutes[proj_with_minutes["TEAM"] == team].sort_values("MIN_WHEN_PLAYING", ascending=False)
    cols = ["ROT_RANK", "ROLE", "PLAYER", "POS", "MIN", "GP", "PROJ_GP", "MIN_WHEN_PLAYING", "MIN_PROJ", "MIN_CHANGE"]
    return g[[c for c in cols if c in g.columns]].round(1)
