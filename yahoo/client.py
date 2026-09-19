"""Optional Yahoo Fantasy integration (rosters, free agents, matchups, positions).

Setup (once):
  1. pip install yahoo_fantasy_api yahoo_oauth
  2. Create an app at https://developer.yahoo.com/apps/  (Fantasy Sports, read)
  3. Save {"consumer_key": "...", "consumer_secret": "..."} to yahoo/oauth2.json
  4. First run opens a browser to authorize; the token is cached in the same file.
"""
import pandas as pd


def connect(league_id: str, year: int = 2026):
    from yahoo_oauth import OAuth2
    import yahoo_fantasy_api as yfa
    sc = OAuth2(None, None, from_file="yahoo/oauth2.json")
    gm = yfa.Game(sc, "nba")
    lg = gm.to_league(f"{gm.game_id()}.l.{league_id}")
    return lg


def rosters(lg) -> pd.DataFrame:
    rows = []
    for t in lg.teams().values():
        tm = lg.to_team(t["team_key"])
        for p in tm.roster():
            rows.append({"FANTASY_TEAM": t["name"], "PLAYER": p["name"],
                         "POS": ",".join(p["eligible_positions"]), "STATUS": p.get("status", "")})
    return pd.DataFrame(rows)


def free_agents(lg, position: str = "Util", n: int = 300) -> list[str]:
    fa = lg.free_agents(position)
    return [p["name"] for p in fa[:n]]


def eligibility(lg) -> pd.DataFrame:
    """Yahoo eligibility for everyone rostered or in the top FA pool."""
    r = rosters(lg)[["PLAYER", "POS"]]
    fa = lg.free_agents("Util")
    f = pd.DataFrame([{"PLAYER": p["name"], "POS": ",".join(p["eligible_positions"])} for p in fa])
    return pd.concat([r, f]).drop_duplicates("PLAYER")


def apply_yahoo_positions(proj: pd.DataFrame, elig: pd.DataFrame) -> pd.DataFrame:
    """Overwrite approximate NBA positions with Yahoo's eligibility where known."""
    m = elig.set_index("PLAYER")["POS"]
    proj = proj.copy()
    proj["POS"] = proj["PLAYER"].map(m).fillna(proj["POS"])
    return proj
