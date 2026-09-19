"""Games per team per fantasy week (Mon-Sun) from the NBA's public schedule JSON."""
import datetime as dt
import json, urllib.request
import pandas as pd

URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json"


def fetch_schedule() -> pd.DataFrame:
    with urllib.request.urlopen(URL, timeout=30) as r:
        js = json.load(r)
    rows = []
    for day in js["leagueSchedule"]["gameDates"]:
        for g in day["games"]:
            if g.get("weekNumber", 0) < 1:      # skip preseason
                continue
            d = dt.datetime.strptime(g["gameDateEst"][:10], "%Y-%m-%d").date()
            rows.append({"date": d, "home": g["homeTeam"]["teamTricode"], "away": g["awayTeam"]["teamTricode"]})
    return pd.DataFrame(rows)


def games_by_team(schedule: pd.DataFrame, week_start: dt.date) -> dict:
    week_end = week_start + dt.timedelta(days=6)
    wk = schedule[(schedule["date"] >= week_start) & (schedule["date"] <= week_end)]
    counts = pd.concat([wk["home"], wk["away"]]).value_counts()
    return counts.to_dict()


def this_week_monday(today: dt.date | None = None) -> dt.date:
    today = today or dt.date.today()
    return today - dt.timedelta(days=today.weekday())


if __name__ == "__main__":
    s = fetch_schedule()
    s.to_csv("data/schedule.csv", index=False)
    print(games_by_team(s, this_week_monday()))
