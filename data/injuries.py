"""Current injury report via ESPN's public NBA injuries feed (no key required)."""
import json, urllib.request
import pandas as pd

URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"


def fetch_injuries() -> pd.DataFrame:
    with urllib.request.urlopen(URL, timeout=30) as r:
        js = json.load(r)
    rows = []
    for team in js.get("injuries", []):
        for inj in team.get("injuries", []):
            rows.append({
                "PLAYER": inj.get("athlete", {}).get("displayName"),
                "TEAM": team.get("displayName"),
                "STATUS": inj.get("status"),
                "DETAIL": (inj.get("longComment") or inj.get("shortComment") or "")[:200],
                "DATE": inj.get("date", "")[:10],
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = fetch_injuries()
    df.to_csv("data/injuries.csv", index=False)
    print(df.head(20).to_string())
