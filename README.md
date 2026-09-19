# 9-Cat Command Center

A draft, roster, matchup, and waiver tool built for a **16-team, 9-category, head-to-head Yahoo league**
(PG/SG/SF/PF/G/F/C/C/UTIL/UTIL, 3 bench, 2 IL, 4 adds per week, snake draft).

## Quick start

```bash
pip install -r requirements.txt
python data/make_sample.py        # fictional demo data so the app runs immediately
streamlit run app.py
```

Then load real data (run these on your own machine; stats.nba.com blocks some cloud IPs):

```bash
python data/fetch_stats.py        # last three seasons of per-game stats -> data/season_*.csv
python data/schedule.py           # NBA schedule -> games per team per fantasy week
python data/injuries.py           # current injury report from ESPN
```

Delete the sample `season_*.csv` files first so they don't get blended in.

## How the rankings work

1. **Projection** (`engine/projections.py`): per-36 rates from the last three seasons blended 55/30/15,
   regressed for games played, scaled to blended minutes. `data/overrides.csv` lets you hand-adjust
   anyone: `MIN_MULT=1.15` for a player stepping into a bigger role, `GP=55` for an injury-prone one,
   `POS=PG,SG` if Yahoo eligibility differs.
2. **Value** (`engine/zscores.py`): z-score per category against the top 208 players (everyone who will be
   rostered in your league). FG% and FT% are volume-weighted so high-attempt shooters move the needle.
   TOV is down-weighted to 0.75 by default.
3. **Punting**: pick a preset or any combination of categories; those z-scores are dropped and the whole
   board re-ranks. The board tab shows how many spots each player moves vs the balanced ranking.
4. **Scarcity** (`engine/positions.py`): value over replacement at each player's best position. With 32
   starting C slots league-wide, C-eligible players carry a premium here.

5. **240-minute rotations** (`engine/minutes.py`): every team's healthy-lineup minutes are forced to sum to
   240 per game. Rotation order uses last season's minutes per game, blended toward what the player's Yahoo
   preseason rank implies when the sample is small, so a star who missed most of last year still starts and a
   4-game fill-in doesn't. Players outside the top 11 drop to spot minutes, individuals cap at 36, and any
   squeeze lands on the bench rather than the starters. Projected games (PROJ_GP) = last season's GP regressed
   halfway toward 65; override it per player in `overrides.csv`. Stats are rescaled per-36 to minutes-when-
   playing. The **Availability weight** slider at the top controls how much PROJ_GP discounts a player
   (AVAIL_VALUE); the draft assistant uses that discounted value.

## Getting data from Yahoo without running fetch scripts

`YAHOO_EXTENSION_PROMPT.md` is a ready-made job for the Claude in Chrome extension. Paste it into the
extension's side panel while signed into Yahoo; it reads your league's Players page (2025-26 per-game
averages, Yahoo eligibility, preseason and current rank, injury tags) and Draft Analysis page (ADP, average
round, % drafted) and downloads `yahoo_players.csv` and `yahoo_adp.csv`. Drop both into `data/` and run
`python data/import_yahoo.py`: it builds `season_2025-26.csv`, fills ADP and Yahoo rank into
`my_rankings.csv`, writes `injuries.csv`, and removes the demo files. Rookies come through with zero
stats; give them a MY_RANK or a MIN_MULT override so they land where you want.

## Players with no usable stats (estimates, clearly labelled)

`data/manual_projections.csv` holds full per-game lines for players the stats can't cover: last season's
injured stars (Haliburton, Irving, Lillard, VanVleet) and this year's rookies. Every row carries
`SOURCE=estimate` and shows that way on the draft board. These are Claude's rough estimates, not data:
edit them freely, and add any player the same way.

## Refreshing ADP and adding X-Rank

See `REFRESH_ADP_AND_XRANK.md`. ADP snapshots live in `data/adp/yahoo_adp_YYYY-MM-DD.csv`; the importer
reads the newest and diffs it against the previous one to produce a MOVE column. X-Rank is read off
Yahoo's draft room on draft day into `data/yahoo_xrank.csv`, or typed straight into the My rankings tab.

## Your own rankings

The **My rankings** tab is an editable table: set `MY_RANK`, `TIER`, `ADP`, and a `NOTE` for any player, then
Save (writes `data/my_rankings.csv`). You can also import a CSV from any site that has a PLAYER column.
The Live draft tab has a "Trust my rankings" slider: at 1.0 your order wins wherever you set one and
unranked players fall in by model rank; at 0.5 it averages the two. ADP, if supplied, drives the
"likely gone" flag instead of the model's guess.

## Draft-day workflow

1. Draft board tab: pick your strategy and export the CSV as a backup.
2. Live draft tab: enter your slot, then log every pick ("Other team took" / "I drafted").
   The recommendation list re-scores after each pick using value + team fit + scarcity + slot legality,
   and flags who probably won't reach your next pick.
3. Decide balanced vs punt by round 3 based on what you've drafted; switching the strategy re-ranks instantly.

- **Player stats**: sortable table (click a column header) with last season per game, last season totals,
  3-year average, this season's projection, or last season vs projected side by side with deltas.
  Filter by name, position, or team.
- **By position**: top players eligible at each roster slot (PG, SG, SF, PF, G, F, C, UTIL) under the current
  strategy, plus a depth table showing how many players clear replacement level at each position.

## In-season

- **My team**: paste your roster, see category strengths and weaknesses under any build.
- **Matchup**: paste both active rosters; projects the 9-cat score using each team's games this week and
  highlights swing categories to stream for.
- **Waivers & streaming**: pickup score = rest-of-season value + fit for your weak categories + a boost for
  4-game weeks. Also lists your drop candidates and the best available players with heavy schedules.
- **Injuries**: current report joined to your rankings so you can spot IL moves and buy-low targets.

## Use it on your phone

See `DEPLOY_TO_PHONE.md`. Short version: push to GitHub, deploy free on Streamlit Community Cloud,
add the URL to your home screen, and switch on **Phone layout** in the app.

## Yahoo integration (optional)

`yahoo/client.py` pulls rosters, free agents, and Yahoo's real position eligibility. See the docstring for
the one-time developer-key setup. Once connected, `apply_yahoo_positions()` overwrites the approximate
NBA positions with Yahoo's.

## Tuning knobs (`config.py`)

`SEASON_WEIGHTS`, `TOV_WEIGHT`, `POOL_SIZE`, `PUNT_PRESETS`, `POSITION_SLOTS`, and in `engine/draft.py`
the `fit_weight` / `scarcity_weight` used in recommendations.
