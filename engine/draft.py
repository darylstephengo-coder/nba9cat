"""Live snake-draft assistant."""
import pandas as pd
import config as C
from engine.zscores import compute_values, category_profile
from engine.positions import parse_pos, can_slot, positional_adjustment
from engine import rankings as R


class Draft:
    def __init__(self, proj: pd.DataFrame, my_slot: int, punts=None):
        self.proj = proj
        self.my_slot = my_slot
        self.punts = list(punts or [])
        self.taken: list[str] = []      # all picks in order
        self.mine: list[str] = []
        self.my_ranks = R.load()
        self.trust = 0.0                # 0 = model only, 1 = my ranks rule where set
        self.avail_weight = 0.5         # 0 = pure per-game value, 1 = fully scaled by projected games
        self.refresh()

    def refresh(self):
        self.board = compute_values(self.proj, self.punts, avail_weight=self.avail_weight)
        self.board["POS_ADJ"] = positional_adjustment(self.board)

    def set_punts(self, punts):
        self.punts = list(punts)
        self.refresh()

    def set_my_ranks(self, mine, trust: float):
        self.my_ranks, self.trust = mine, float(trust)

    # ---- draft flow -------------------------------------------------------
    @property
    def pick_number(self):
        return len(self.taken) + 1

    def picks_until_mine(self):
        """How many picks happen before my next turn in a snake."""
        n = C.TEAMS
        p = self.pick_number
        rnd, pos = divmod(p - 1, n)
        order = list(range(1, n + 1)) if rnd % 2 == 0 else list(range(n, 0, -1))
        cur = order[pos]
        if cur == self.my_slot:
            return 0
        # simulate forward
        k = 0
        while True:
            k += 1
            rnd, pos = divmod(p - 1 + k, n)
            order = list(range(1, n + 1)) if rnd % 2 == 0 else list(range(n, 0, -1))
            if order[pos] == self.my_slot:
                return k

    def take(self, player: str, mine: bool = False):
        if player not in set(self.board["PLAYER"]):
            raise ValueError(f"Unknown player: {player}")
        self.taken.append(player)
        if mine:
            self.mine.append(player)

    NICKNAMES = {
        "wemby": "Victor Wembanyama", "joker": "Nikola Jokic", "dame": "Damian Lillard",
        "bron": "LeBron James", "greek": "Giannis Antetokounmpo", "freak": "Giannis Antetokounmpo",
        "ant": "Anthony Edwards", "antman": "Anthony Edwards", "melo": "LaMelo Ball",
        "beard": "James Harden", "klaw": "Kawhi Leonard", "spida": "Donovan Mitchell",
        "book": "Devin Booker", "bam": "Bam Adebayo", "kp": "Kristaps Porzingis",
        "zion": "Zion Williamson", "ja": "Ja Morant", "cade": "Cade Cunningham",
        "flagg": "Cooper Flagg", "trae": "Trae Young", "luka": "Luka Doncic",
    }

    def find(self, text: str, limit: int = 6) -> list:
        """Match typed text against available players. Best guess first.

        Ranks: exact name, last name starts with, any word starts with, contains.
        """
        import re, unicodedata

        def norm(x):
            x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode()
            x = x.lower().replace("-", " ").replace(".", " ").replace("'", "")
            return re.sub(r"[^a-z ]", " ", x).split() and " ".join(re.sub(r"[^a-z ]", " ", x).split()) or ""

        q = norm(text)
        if not q:
            return []
        nick = self.NICKNAMES.get(q)
        hits = []
        for _, row in self.available().iterrows():
            name = row["PLAYER"]
            n = norm(name)
            parts = n.split()
            initials = "".join(w[0] for w in parts if w)
            if n == q or (nick and norm(nick) == n):
                score = 0
            elif initials == q and len(q) >= 2:      # sga, kat, jjj, mpj
                score = 1
            elif parts and parts[-1].startswith(q):
                score = 1.5
            elif any(w.startswith(q) for w in parts):
                score = 2
            elif n.startswith(q):
                score = 3
            elif q in n:
                score = 4
            elif len(q) >= 4 and q[:4] in n.replace(" ", ""):
                score = 5
            else:
                continue
            hits.append((score, float(row.get("MY_VALUE", 9999) or 9999), name, row["POS"], row.get("ADP")))
        hits.sort(key=lambda h: (h[0], h[1]))
        return hits[:limit]

    def set_status(self, player: str, taken: bool, mine: bool):
        """Tick-box control: set whether a player is taken and whether by me. Order-agnostic."""
        if mine:
            taken = True
        if taken and player not in self.taken:
            self.taken.append(player)
        if not taken and player in self.taken:
            self.taken.remove(player)
        if mine and player not in self.mine:
            self.mine.append(player)
        if not mine and player in self.mine:
            self.mine.remove(player)

    def undo(self):
        if self.taken:
            p = self.taken.pop()
            if self.mine and self.mine[-1] == p:
                self.mine.pop()

    # ---- recommendations --------------------------------------------------
    def my_roster(self) -> pd.DataFrame:
        return self.board[self.board["PLAYER"].isin(self.mine)]

    def available(self) -> pd.DataFrame:
        return self.board[~self.board["PLAYER"].isin(self.taken)]

    def recommend(self, n: int = 15, fit_weight: float = 0.35, scarcity_weight: float = 0.25) -> pd.DataFrame:
        """Best available, blending raw value, team-fit, and positional scarcity.

        FIT: for a balanced build, reward cats where my roster is weakest.
             for a punt build, punted cats are already excluded from VALUE.
        LEGAL: whether I can still roster this player without breaking slot rules.
        """
        avail = self.available().copy()
        mine = self.my_roster()
        prof = category_profile(mine)
        live_cats = [c for c in C.ALL_CATS if c not in self.punts]
        if len(mine) >= 2:
            # weakness weights: cats below my average get more weight
            centered = prof[live_cats] - prof[live_cats].mean()
            need = (-centered).clip(lower=0)
            need = need / need.sum() if need.sum() > 0 else need
            avail["FIT"] = sum(avail[f"z_{c}"] * need[c] for c in live_cats) * len(live_cats)
        else:
            avail["FIT"] = 0.0
        my_pos = [parse_pos(p) for p in mine["POS"]]
        avail["LEGAL"] = avail["POS"].apply(lambda p: can_slot(my_pos + [parse_pos(p)]))
        avail["SCORE"] = (avail["AVAIL_VALUE"] + fit_weight * avail["FIT"]
                          + scarcity_weight * avail["POS_ADJ"])
        avail.loc[~avail["LEGAL"], "SCORE"] -= 100
        avail = R.blend(avail, self.my_ranks, self.trust, score_col="SCORE")
        avail = avail[~avail["AVOID"]]                      # do-not-draft list
        # will they last until my next pick? ADP if you supplied it, else balanced rank
        gap = self.picks_until_mine()
        picks_before_mine = len(self.taken) + gap
        proxy = avail["ADP"].where(avail["ADP"].notna(), avail["TOTAL"].rank(ascending=False))
        avail["LIKELY_GONE"] = proxy <= picks_before_mine
        cols = ["BLEND_RANK", "RANK", "MY_RANK", "TIER", "PLAYER", "TEAM", "POS", "SCORE", "VALUE", "AVAIL_VALUE",
                "PROJ_GP", "FIT", "POS_ADJ", "LEGAL", "LIKELY_GONE", "ADP", "YAHOO_RANK", "X_RANK", "NOTE"]
        cols = [c for c in cols if c in avail.columns]
        return avail.sort_values("BLEND_RANK").head(n)[cols].round(2)

    def team_summary(self) -> pd.Series:
        return category_profile(self.my_roster()).round(2)
