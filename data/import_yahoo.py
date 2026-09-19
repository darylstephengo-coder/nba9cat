"""Turn the two CSVs collected by the Claude in Chrome extension into the app's data files.

Input (in data/):
  yahoo_players.csv  PLAYER,TEAM,POS,STATUS,PRE_RANK,CUR_RANK,PCT_OWNED,GP,MIN,FGM,FGA,FG_PCT,
                     FTM,FTA,FT_PCT,FG3M,PTS,REB,AST,STL,BLK,TOV
  yahoo_adp.csv      PLAYER,TEAM,POS,ADP,AVG_ROUND,PCT_DRAFTED[,X_RANK]

Output:
  data/season_2025-26.csv   per-game stats in the app's schema (replaces any demo/nba_api file)
  data/my_rankings.csv      ADP, Yahoo preseason rank (and X-Rank if present) merged into your rankings
  data/injuries.csv         players with a Yahoo injury tag

Usage:  python data/import_yahoo.py
"""
import glob, os, re, sys
import pandas as pd

D = os.path.dirname(os.path.abspath(__file__))
SEASON = "2025-26"

TEAM_FIX = {"GS": "GSW", "NY": "NYK", "NO": "NOP", "SA": "SAS", "PHO": "PHX", "WSH": "WAS", "UTAH": "UTA"}


def _num(s):
    if pd.isna(s):
        return pd.NA
    s = str(s).strip().replace("%", "").replace(",", "")
    if s in ("", "-", "–", "—", "nan"):
        return pd.NA
    if ":" in s:                                   # Yahoo minutes come as mm:ss
        m, sec = s.split(":")[:2]
        return round(float(m) + float(sec) / 60, 2)
    try:
        return float(s)
    except ValueError:
        return pd.NA


# Yahoo truncates long names in the table; expand the common ones and strip accents so names
# match across files and are easy to type in the app.
NAME_FIX = {
    "G. Antetokounmpo": "Giannis Antetokounmpo",
    "N. Alexander-Walker": "Nickeil Alexander-Walker",
    "S. Gilgeous-Alexander": "Shai Gilgeous-Alexander",
    "K. Caldwell-Pope": "Kentavious Caldwell-Pope",
    "S. Mamukelashvili": "Sandro Mamukelashvili",
    "T. Shannon Jr.": "Terrence Shannon Jr.",
    "D. Finney-Smith": "Dorian Finney-Smith",
    "O. Prosper": "Olivier-Maxence Prosper",
    "Y. Konan Niederhauser": "Yanic Konan Niederhauser",
    "C. Murray-Boyles": "Collin Murray-Boyles",
    "T. Hardaway Jr.": "Tim Hardaway Jr.",
}


def clean_name(n):
    import unicodedata
    n = str(n).strip()
    n = NAME_FIX.get(n, n)
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode()
    return n


def _split_made_att(df, made, att):
    """Handle a combined 'FGM/A' column if the extension left it that way."""
    for col in list(df.columns):
        if re.fullmatch(rf"{made}\s*/\s*A|{made}M?/A|{made}-A", col.strip(), re.I):
            parts = df[col].astype(str).str.split(r"[/-]", expand=True)
            df[made] = parts[0].map(_num)
            df[att] = parts[1].map(_num) if parts.shape[1] > 1 else pd.NA
            df = df.drop(columns=[col])
    return df


def load_players():
    p = os.path.join(D, "yahoo_players.csv")
    if not os.path.exists(p):
        sys.exit("data/yahoo_players.csv not found: run the extension prompt first.")
    df = pd.read_csv(p, dtype=str)
    df.columns = [c.strip().upper() for c in df.columns]
    df = df.rename(columns={"3PTM": "FG3M", "3PM": "FG3M", "ST": "STL", "TO": "TOV", "MPG": "MIN",
                            "FG%": "FG_PCT", "FT%": "FT_PCT", "NAME": "PLAYER"})
    df = _split_made_att(df, "FGM", "FGA")
    df = _split_made_att(df, "FTM", "FTA")
    for made, att in [("FGM", "FGA"), ("FTM", "FTA")]:          # "10.5/18.9" left inside the made column
        if made in df.columns:
            m = df[made].astype(str).str.contains("/")
            if m.any():
                parts = df.loc[m, made].str.split("/", expand=True)
                df.loc[m, made] = parts[0]
                if att not in df.columns:
                    df[att] = pd.NA
                df.loc[m, att] = parts[1]
    for c in ["PRE_RANK", "CUR_RANK", "PCT_OWNED", "GP", "MIN", "FGM", "FGA", "FG_PCT", "FTM", "FTA",
              "FT_PCT", "FG3M", "PTS", "REB", "AST", "STL", "BLK", "TOV"]:
        if c in df.columns:
            df[c] = df[c].map(_num)
        else:
            df[c] = pd.NA
    df["PLAYER"] = df["PLAYER"].map(clean_name)
    df["TEAM"] = df["TEAM"].str.strip().str.upper().replace(TEAM_FIX)
    df["POS"] = df["POS"].str.replace(" ", "").str.upper()
    return df


def write_season(df):
    stats = df.copy()          # rookies with blank stats stay in (as zeros) so they appear on the board
    adp_path = latest_adp_path()
    if os.path.exists(adp_path):   # players who exist only in draft analysis (this year's rookies) join with zero stats
        adp = pd.read_csv(adp_path, dtype=str)
        adp.columns = [c.strip().upper() for c in adp.columns]
        adp["PLAYER"] = adp["PLAYER"].map(clean_name)
        adp["TEAM"] = adp["TEAM"].str.strip().str.upper().replace(TEAM_FIX)
        moved = stats.merge(adp[["PLAYER", "TEAM"]], on="PLAYER", how="left", suffixes=("", "_ADP"))
        chg = moved["TEAM_ADP"].notna() & (moved["TEAM_ADP"] != moved["TEAM"])
        if chg.any():
            for _, r in moved[chg].iterrows():
                print(f"team update from ADP page: {r['PLAYER']} {r['TEAM']} -> {r['TEAM_ADP']}")
            stats["TEAM"] = moved["TEAM_ADP"].where(chg, stats["TEAM"]).values
        extra = adp[~adp["PLAYER"].isin(stats["PLAYER"])][["PLAYER", "TEAM", "POS"]].copy()
        extra["TEAM"] = extra["TEAM"].str.strip().str.upper().replace(TEAM_FIX)
        extra["POS"] = extra["POS"].str.replace(" ", "").str.upper()
        if len(extra):
            stats = pd.concat([stats, extra], ignore_index=True)
            print(f"added {len(extra)} players found only in draft analysis (rookies / no 2025-26 stats)")
    xr_path = os.path.join(D, "yahoo_xrank.csv")          # ranked by Yahoo but nowhere else
    if os.path.exists(xr_path):
        xr = pd.read_csv(xr_path, dtype=str)
        xr.columns = [c.strip().upper() for c in xr.columns]
        xr["PLAYER"] = match_to_roster(xr["PLAYER"].map(clean_name), stats["PLAYER"])
        miss = xr[~xr["PLAYER"].isin(stats["PLAYER"])][["PLAYER"]].drop_duplicates()
        if len(miss):
            print(f"added {len(miss)} more from the X-Rank list: {', '.join(miss['PLAYER'].head(8))}")
            stats = pd.concat([stats, miss], ignore_index=True)
    # if only percentages were captured, back out made from attempts
    for made, att, pct in [("FGM", "FGA", "FG_PCT"), ("FTM", "FTA", "FT_PCT")]:
        m = stats[made].isna() & stats[att].notna() & stats[pct].notna()
        p = stats.loc[m, pct].astype(float)
        p = p.where(p <= 1, p / 100)
        stats.loc[m, made] = stats.loc[m, att].astype(float) * p
    out = pd.DataFrame({
        "PLAYER": stats["PLAYER"],
        "PLAYER_ID": stats["PLAYER"].map(lambda n: abs(hash(n)) % 10**8),
        "TEAM": stats["TEAM"], "POS": stats["POS"], "SEASON": SEASON,
        "GP": stats["GP"], "MIN": stats["MIN"], "PTS": stats["PTS"], "FG3M": stats["FG3M"],
        "REB": stats["REB"], "AST": stats["AST"], "STL": stats["STL"], "BLK": stats["BLK"],
        "TOV": stats["TOV"], "FGM": stats["FGM"], "FGA": stats["FGA"], "FTM": stats["FTM"], "FTA": stats["FTA"],
        "PRIOR_RANK": stats["PRE_RANK"] if "PRE_RANK" in stats.columns else pd.NA,
    })
    out = out.fillna({c: 0 for c in out.columns if c != "PRIOR_RANK"})
    path = os.path.join(D, f"season_{SEASON}.csv")
    out.to_csv(path, index=False)
    print(f"wrote {path}: {len(out)} players ({int((out['GP'] > 0).sum())} with 2025-26 stats)")
    return out


def latest_adp_path():
    """Newest dated snapshot in data/adp/, else the plain data/yahoo_adp.csv."""
    snap_dir = os.path.join(D, "adp")
    snaps = sorted(glob.glob(os.path.join(snap_dir, "yahoo_adp_*.csv")))
    return snaps[-1] if snaps else os.path.join(D, "yahoo_adp.csv")


def previous_adp():
    """Second-newest snapshot, for the ADP movement column."""
    snaps = sorted(glob.glob(os.path.join(D, "adp", "yahoo_adp_*.csv")))
    if len(snaps) < 2:
        return None
    prev = pd.read_csv(snaps[-2], dtype=str)
    prev.columns = [c.strip().upper() for c in prev.columns]
    prev["PLAYER"] = prev["PLAYER"].map(clean_name)
    prev["ADP_PREV"] = prev["ADP"].map(_num)
    print(f"comparing against previous snapshot {os.path.basename(snaps[-2])}")
    return prev[["PLAYER", "ADP_PREV"]]


def _key(n):
    """Match key: accent-free, case-free, punctuation-free."""
    import unicodedata
    n = unicodedata.normalize("NFKD", str(n)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", n.lower())


def match_to_roster(names: pd.Series, roster: pd.Series) -> pd.Series:
    """Map incoming names (any case) to the spelling already used in the season file."""
    lookup = {_key(n): n for n in roster}
    return names.map(lambda n: lookup.get(_key(n), str(n).strip()))


def load_xrank(roster: pd.Series | None = None):
    """data/yahoo_xrank.csv: PLAYER,X_RANK — read off Yahoo's draft room, which is the only place it exists."""
    p = os.path.join(D, "yahoo_xrank.csv")
    if not os.path.exists(p):
        return None
    x = pd.read_csv(p, dtype=str)
    x.columns = [c.strip().upper() for c in x.columns]
    x["PLAYER"] = x["PLAYER"].map(clean_name)
    if roster is not None:
        before = set(x["PLAYER"])
        x["PLAYER"] = match_to_roster(x["PLAYER"], roster)
        unmatched = [n for n in x["PLAYER"] if _key(n) not in {_key(r) for r in roster}]
        if unmatched:
            print(f"X-Rank names not on the roster ({len(unmatched)}): {', '.join(unmatched[:8])}")
    x["X_RANK"] = x["X_RANK"].map(_num)
    if "ADP_PRERANK" in x.columns:
        x["ADP_PRERANK"] = x["ADP_PRERANK"].map(_num)
        keep = ["PLAYER", "X_RANK", "ADP_PRERANK"]
    else:
        keep = ["PLAYER", "X_RANK"]
    print(f"read X-Rank for {int(x['X_RANK'].notna().sum())} players")
    return x[keep].dropna(subset=["X_RANK"])


def write_rankings(df):
    adp_path = latest_adp_path()
    ranks = df[["PLAYER", "PRE_RANK"]].rename(columns={"PRE_RANK": "YAHOO_RANK"})
    if os.path.exists(adp_path):
        print(f"reading ADP from {os.path.relpath(adp_path, D)}")
        adp = pd.read_csv(adp_path, dtype=str)
        adp.columns = [c.strip().upper() for c in adp.columns]
        adp["PLAYER"] = adp["PLAYER"].map(clean_name)
        for c in ["ADP", "AVG_ROUND", "PCT_DRAFTED", "X_RANK"]:
            if c in adp.columns:
                adp[c] = adp[c].map(_num)
        if "PCT_DRAFTED" in adp.columns:
            thin = int((adp["PCT_DRAFTED"] < 25).sum())
            print(f"note: {thin} players have ADP from <25% of leagues — see the PCT_DRAFTED column")
        keep = ["PLAYER", "ADP"] + [c for c in ["PCT_DRAFTED", "ADP_PREV", "X_RANK"] if c in adp.columns]
        prev = previous_adp()
        if prev is not None:
            adp = adp.merge(prev, on="PLAYER", how="left")
            keep = keep + ["ADP_PREV"] if "ADP_PREV" not in keep else keep
        ranks = ranks.merge(adp[[c for c in keep if c in adp.columns]], on="PLAYER", how="outer")
        print(f"read {adp_path}: {len(adp)} rows")
    else:
        ranks["ADP"] = pd.NA
        print("no yahoo_adp.csv found: skipping ADP")
    roster = set(df["PLAYER"])
    for extra_file in ["manual_projections.csv", "season_2025-26.csv"]:
        fp = os.path.join(D, extra_file)
        if os.path.exists(fp):
            roster |= set(pd.read_csv(fp)["PLAYER"].map(clean_name))
    xr = load_xrank(roster=pd.Series(sorted(roster)))
    if xr is not None:
        ranks = ranks.drop(columns=[c for c in ["X_RANK", "ADP_PRERANK"] if c in ranks.columns]).merge(xr, on="PLAYER", how="outer")
    if "X_RANK" not in ranks.columns:
        ranks["X_RANK"] = pd.NA
    if "ADP_PREV" not in ranks.columns:
        ranks["ADP_PREV"] = pd.NA
    if "ADP_PRERANK" in ranks.columns:   # pre-rank page ADP: same numbers, wider coverage
        ranks["ADP"] = pd.to_numeric(ranks["ADP"], errors="coerce")
        ranks["ADP_PRERANK"] = pd.to_numeric(ranks["ADP_PRERANK"], errors="coerce")
        n_filled = int((ranks["ADP"].isna() & ranks["ADP_PRERANK"].notna()).sum())
        ranks["ADP"] = ranks["ADP"].fillna(ranks["ADP_PRERANK"])
        if n_filled:
            print(f"filled ADP for {n_filled} more players from the pre-rank page")
        ranks = ranks.drop(columns=["ADP_PRERANK"])
    my_path = os.path.join(D, "my_rankings.csv")
    mine = pd.read_csv(my_path) if os.path.exists(my_path) else pd.DataFrame(columns=["PLAYER"])
    for c in ["MY_RANK", "TIER", "NOTE", "AVOID"]:
        if c not in mine.columns:
            mine[c] = pd.NA
    merged = ranks.merge(mine[["PLAYER", "MY_RANK", "TIER", "NOTE", "AVOID"]], on="PLAYER", how="outer")
    merged["NOTE"] = merged["NOTE"].fillna("")
    if "AVOID" not in mine.columns:
        mine["AVOID"] = False
    cols_out = ["PLAYER", "MY_RANK", "TIER", "ADP", "PCT_DRAFTED", "ADP_PREV", "YAHOO_RANK", "X_RANK",
                "AVOID", "NOTE"]
    merged = merged[[c for c in cols_out if c in merged.columns]]
    merged.to_csv(my_path, index=False)
    print(f"wrote {my_path}: {merged['ADP'].notna().sum()} with ADP, {merged['YAHOO_RANK'].notna().sum()} with Yahoo rank")


def write_injuries(df):
    if "STATUS" not in df.columns:
        return
    inj = df[df["STATUS"].fillna("").str.strip() != ""][["PLAYER", "TEAM", "STATUS"]].copy()
    inj["DETAIL"], inj["DATE"] = "", ""
    inj.to_csv(os.path.join(D, "injuries.csv"), index=False)
    print(f"wrote data/injuries.csv: {len(inj)} tagged players")


if __name__ == "__main__":
    players = load_players()
    for f in os.listdir(D):                      # remove demo seasons so they don't blend in
        if f.startswith("season_") and f.endswith(".csv") and SEASON not in f:
            demo = pd.read_csv(os.path.join(D, f), nrows=3)
            if demo["PLAYER"].str.contains(r"\d\d$").all():
                os.remove(os.path.join(D, f)); print("removed demo file", f)
    write_season(players)
    write_rankings(players)
    write_injuries(players)
    print("done. Restart the app: streamlit run app.py")
