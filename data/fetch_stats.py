"""Pull the last three seasons of per-game stats from stats.nba.com via nba_api.

Usage (from the project root):
    python data/fetch_stats.py                # seasons ending 2026, 2025, 2024
    python data/fetch_stats.py 2025-26 2024-25

Writes data/season_<YYYY-YY>.csv. Run this on your own machine (stats.nba.com
blocks some cloud IPs). Re-run in-season to refresh current-year stats.
"""
import sys, time
import pandas as pd
from nba_api.stats.endpoints import leaguedashplayerstats, commonallplayers

NBA_POS_TO_YAHOO = {
    "G": "PG,SG", "F": "SF,PF", "C": "C",
    "G-F": "SG,SF", "F-G": "SF,SG", "F-C": "PF,C", "C-F": "C,PF",
}


def fetch_season(season: str) -> pd.DataFrame:
    df = leaguedashplayerstats.LeagueDashPlayerStats(
        season=season, per_mode_detailed="PerGame", season_type_all_star="Regular Season"
    ).get_data_frames()[0]
    df = df.rename(columns={"PLAYER_NAME": "PLAYER", "TEAM_ABBREVIATION": "TEAM"})
    keep = ["PLAYER", "PLAYER_ID", "TEAM", "GP", "MIN", "PTS", "FG3M", "REB", "AST",
            "STL", "BLK", "TOV", "FGM", "FGA", "FTM", "FTA"]
    df = df[keep].copy()
    df["SEASON"] = season
    return df


def fetch_positions() -> pd.DataFrame:
    """Approximate Yahoo eligibility from NBA listed positions. Yahoo's own
    eligibility is better: use yahoo/client.py to overwrite POS when available."""
    from nba_api.stats.endpoints import commonteamroster
    from nba_api.stats.static import teams
    rows = []
    for t in teams.get_teams():
        try:
            r = commonteamroster.CommonTeamRoster(team_id=t["id"]).get_data_frames()[0]
            for _, p in r.iterrows():
                rows.append({"PLAYER_ID": p["PLAYER_ID"], "CUR_TEAM": t["abbreviation"],
                             "POS": NBA_POS_TO_YAHOO.get(p["POSITION"], "SF,PF")})
            time.sleep(0.6)
        except Exception as e:
            print("roster fetch failed for", t["abbreviation"], e)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    seasons = sys.argv[1:] or ["2025-26", "2024-25", "2023-24"]
    pos = fetch_positions()
    for s in seasons:
        df = fetch_season(s).merge(pos, on="PLAYER_ID", how="left")
        df["POS"] = df["POS"].fillna("SF,PF")
        df["TEAM"] = df["CUR_TEAM"].fillna(df["TEAM"])   # current roster, so trades are reflected
        df = df.drop(columns=["CUR_TEAM"])
        out = f"data/season_{s}.csv"
        df.to_csv(out, index=False)
        print(f"wrote {out}: {len(df)} players")
        time.sleep(1)
