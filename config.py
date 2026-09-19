"""League settings. Values here are defaults; the app overwrites them at runtime from
data/leagues.json so you can keep several leagues with different settings.
"""
BASE_POS = ["PG", "SG", "SF", "PF", "C"]

SLOT_ELIGIBILITY = {
    "PG": {"PG"}, "SG": {"SG"}, "SF": {"SF"}, "PF": {"PF"},
    "G": {"PG", "SG"}, "F": {"SF", "PF"}, "C": {"C"},
    "G/F": {"PG", "SG", "SF", "PF"}, "F/C": {"SF", "PF", "C"},
    "UTIL": {"PG", "SG", "SF", "PF", "C"},
}

TEAMS = 16
ROSTER_SLOTS = {"PG": 1, "SG": 1, "SF": 1, "PF": 1, "G": 1, "F": 1, "C": 2, "UTIL": 2}
BENCH = 3
IL = 2
ADDS_PER_WEEK = 4

# The nine categories
COUNTING_CATS = ["FG3M", "PTS", "REB", "AST", "STL", "BLK", "TOV"]
PCT_CATS = {"FG_PCT": ("FGM", "FGA"), "FT_PCT": ("FTM", "FTA")}
ALL_CATS = ["FG_PCT", "FT_PCT"] + COUNTING_CATS
NEGATIVE_CATS = {"TOV"}
CAT_LABEL = {"FG_PCT": "FG%", "FT_PCT": "FT%", "FG3M": "3PM", "PTS": "PTS", "REB": "REB",
             "AST": "AST", "STL": "STL", "BLK": "BLK", "TOV": "TO"}

TOV_WEIGHT = 0.75

# Players with no 2025-26 stats can't be modelled, so they're ranked from the market
# (Yahoo X-Rank and ADP) and then pushed down by these amounts.
#   INJ    — missed the whole season with a serious injury: ramp-up, minutes limits, rust.
#   ROOKIE — no NBA record: rookies usually hurt FG%, FT% and turnovers in 9-cat.
INJ_DISCOUNT = 0.20
ROOKIE_DISCOUNT = 0.35

PUNT_PRESETS = {
    "Balanced": [],
    "Punt FT%": ["FT_PCT"],
    "Punt FG%": ["FG_PCT"],
    "Punt AST": ["AST"],
    "Punt PTS": ["PTS"],
    "Punt TOV": ["TOV"],
    "Punt FT% + TOV": ["FT_PCT", "TOV"],
    "Punt FG% + BLK": ["FG_PCT", "BLK"],
    "Punt AST + TOV": ["AST", "TOV"],
    "Punt PTS + TOV": ["PTS", "TOV"],
}

SEASON_WEIGHTS = [0.55, 0.30, 0.15]
MIN_GP_FOR_FULL_WEIGHT = 40


def _derive():
    """Recompute everything that depends on TEAMS / ROSTER_SLOTS / BENCH."""
    g = globals()
    g["ACTIVE_SIZE"] = sum(ROSTER_SLOTS.values())
    g["ROSTER_SIZE"] = g["ACTIVE_SIZE"] + BENCH
    g["POOL_SIZE"] = TEAMS * g["ROSTER_SIZE"]
    slots = {p: 0.0 for p in BASE_POS}
    for s, n in ROSTER_SLOTS.items():
        elig = SLOT_ELIGIBILITY.get(s, set())
        if not elig:
            continue
        for p in elig:
            slots[p] += n / len(elig)
    g["POSITION_SLOTS"] = {p: v * TEAMS for p, v in slots.items() if v > 0}


def apply_league(lg: dict) -> None:
    """Point the whole engine at one league's settings."""
    g = globals()
    g["TEAMS"] = int(lg.get("teams", 16))
    g["ROSTER_SLOTS"] = {k: int(v) for k, v in lg.get("slots", ROSTER_SLOTS).items() if int(v) > 0}
    g["BENCH"] = int(lg.get("bench", 3))
    g["IL"] = int(lg.get("il", 2))
    g["ADDS_PER_WEEK"] = int(lg.get("adds", 4))
    _derive()


_derive()
