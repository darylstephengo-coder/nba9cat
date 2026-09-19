"""Generate synthetic demo data so the app runs before you fetch real stats.
Players are fictional archetypes ("Elite PG 01"). Replace with fetch_stats.py output."""
import numpy as np, pandas as pd
rng = np.random.default_rng(7)

ARCH = {  # name: (POS, MIN, PTS, 3PM, REB, AST, STL, BLK, TOV, FG%, FGA, FT%, FTA, count)
    "Star PG":     ("PG",     35, 26, 3.0,  4.5, 8.5, 1.4, 0.4, 3.4, .47, 19, .87, 7, 8),
    "Star Wing":   ("SF,PF",  35, 27, 2.6,  7.5, 5.5, 1.3, 0.7, 3.0, .49, 19, .82, 6, 10),
    "Star Big":    ("C",      33, 24, 0.8, 11.5, 3.5, 0.9, 1.8, 2.8, .58, 16, .70, 7, 8),
    "Scoring G":   ("SG,SF",  32, 20, 2.8,  3.8, 3.5, 1.0, 0.3, 2.2, .45, 16, .84, 4, 20),
    "Floor PG":    ("PG,SG",  30, 13, 1.8,  3.2, 6.5, 1.2, 0.2, 2.0, .44, 11, .82, 2.5, 20),
    "3&D Wing":    ("SG,SF",  29, 12, 2.4,  4.5, 1.8, 1.1, 0.5, 1.0, .46, 9, .80, 1.5, 40),
    "Glue F":      ("SF,PF",  28, 11, 1.3,  6.0, 2.5, 0.9, 0.7, 1.4, .50, 9, .75, 2, 40),
    "Rim Big":     ("C",      27, 11, 0.1,  9.5, 1.5, 0.6, 1.6, 1.4, .64, 7, .62, 3.5, 24),
    "Stretch Big": ("PF,C",   26, 12, 1.9,  6.5, 1.8, 0.6, 0.9, 1.2, .48, 9, .80, 2, 24),
    "Bench G":     ("PG,SG",  20,  8, 1.2,  2.2, 2.8, 0.7, 0.2, 1.2, .43, 7, .80, 1.5, 50),
    "Bench F":     ("SF,PF",  19,  7, 0.9,  3.8, 1.3, 0.6, 0.5, 0.9, .47, 6, .74, 1.5, 50),
    "Bench C":     ("C",      17,  6, 0.2,  5.0, 1.0, 0.4, 0.9, 0.8, .58, 4.5, .65, 2, 30),
}

def season(label, noise):
    rows = []
    for name, (pos, mn, pts, tpm, reb, ast, stl, blk, tov, fgp, fga, ftp, fta, n) in ARCH.items():
        for i in range(n):
            s = rng.normal(1, noise)
            gp = int(np.clip(rng.normal(65, 12), 20, 82))
            fga_ = fga * s; fta_ = fta * s
            fgp_ = np.clip(fgp + rng.normal(0, .025), .35, .75)
            ftp_ = np.clip(ftp + rng.normal(0, .04), .45, .95)
            rows.append(dict(PLAYER=f"{name} {i+1:02d}", PLAYER_ID=abs(hash(f"{name}{i}")) % 10**7,
                TEAM=rng.choice(["ATL","BOS","BKN","CHA","CHI","CLE","DAL","DEN","DET","GSW","HOU","IND","LAC","LAL","MEM","MIA","MIL","MIN","NOP","NYK","OKC","ORL","PHI","PHX","POR","SAC","SAS","TOR","UTA","WAS"]),
                POS=pos, SEASON=label, GP=gp, MIN=round(mn*s,1), PTS=round(pts*s,1), FG3M=round(tpm*s,1),
                REB=round(reb*s,1), AST=round(ast*s,1), STL=round(stl*s,2), BLK=round(blk*s,2), TOV=round(tov*s,1),
                FGM=round(fga_*fgp_,1), FGA=round(fga_,1), FTM=round(fta_*ftp_,1), FTA=round(fta_,1)))
    return pd.DataFrame(rows)

if __name__ == "__main__":
    rng2 = np.random.default_rng(7)
    for lab, noise in [("2025-26", .12), ("2024-25", .14), ("2023-24", .16)]:
        rng = np.random.default_rng(int(lab[:4]))
        season(lab, noise).to_csv(f"data/season_{lab}.csv", index=False)
    print("sample seasons written")
