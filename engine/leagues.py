"""Saved league settings, so you can switch between leagues with different rosters."""
import json, os
import config as C

PATH = "data/leagues.json"

DEFAULT = {
    "name": "League 1",
    "teams": 16,
    "slots": {"PG": 1, "SG": 1, "SF": 1, "PF": 1, "G": 1, "F": 1, "C": 2, "UTIL": 2},
    "bench": 3, "il": 2, "adds": 4, "draft_slot": 1, "strategy": "Balanced",
}


def load() -> list:
    if os.path.exists(PATH):
        try:
            data = json.load(open(PATH))
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass
    return [dict(DEFAULT)]


def save(leagues: list) -> None:
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    json.dump(leagues, open(PATH, "w"), indent=2)


def blank(name: str) -> dict:
    lg = dict(DEFAULT)
    lg["slots"] = dict(DEFAULT["slots"])
    lg["name"] = name
    return lg


def activate(lg: dict) -> None:
    C.apply_league(lg)


def describe(lg: dict) -> str:
    slots = " · ".join(f"{n}×{s}" if n > 1 else s for s, n in lg["slots"].items())
    return (f"{lg['teams']} teams · {slots} · {lg['bench']} BN · {lg['il']} IL · "
            f"{sum(lg['slots'].values()) + lg['bench']}-man roster")
