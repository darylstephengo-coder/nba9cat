# Start here

Everything you need, in order. The app already contains real Yahoo data: 392 players, 2025-26 stats,
Yahoo eligibility, ADP as of 16 September, and injury tags. Nothing needs fetching to start using it.

---

## 1. Open the app (once, ~10 minutes the first time)

1. Install Python 3 from python.org. On Windows, tick **"Add python.exe to PATH"** on the first screen.
2. Unzip `nba9cat.zip` somewhere easy to find, like Documents.
3. Open a terminal inside the `nba9cat` folder.
   - Windows: right-click empty space in the folder → **Open in Terminal**
   - Mac: open Terminal, type `cd ` (with a space), drag the folder in, press Enter
4. Run once: `pip install -r requirements.txt`
5. Run: `streamlit run app.py`

The browser opens at http://localhost:8501. Leave the terminal open while you use it. To stop, press
Ctrl+C. Next time, only steps 3 and 5 are needed.

---

## 2. Find your way around

The **sidebar on the left** controls everything:

- **League** — pick which of your leagues you're working on.
- **Tool** — *Draft tool*, *Season tool*, or *League settings*.
- **Strategy** — Balanced, or a punt build. Changing it re-ranks every player.
- **My draft pick number** — your slot in round 1.
- **Advanced settings** — leave these alone unless you want to tinker.

### League settings (do this first)

You have three leagues with different rosters. Open **League settings**, set the number of teams,
how many of each starting slot (PG, SG, SF, PF, C, G, F, G/F, F/C, UTIL — set unused ones to 0),
bench, IL, and adds per week. Press **Save settings**. Then **Add another league** and repeat.
Everything in both tools follows whichever league is selected in the sidebar.

### Draft tool

- **Board** — every player with three reference numbers side by side: **ADP** (where people actually
  draft him), **XRANK** (Yahoo's experts), **MY_RANK** (yours), plus all nine categories. Use the
  "Stats to show" switch to flip between last season per game, last season totals, 3-year average, and
  projected. Search by name, filter by position, and tick **TAKEN** / **MINE** as picks happen.
  Underneath: best picks for you right now, and your roster's category strengths.
- **My rankings** — type your own rank for players you feel strongly about, tick AVOID for players you
  refuse to draft, then press Save. Blank ranks are fine; the model fills the gaps.
- **Plan** — your 13 pick numbers and who should still be there at each.
- **Compare** — 2 to 4 players side by side, best number in each row highlighted.

### Season tool

My team, This week (matchup projection), Waivers, Injuries, Rotations, All players.

## 3. Refresh data before each draft (10 minutes per draft)

See `REFRESH_ADP_AND_XRANK.md` for the two extension jobs.

- **Night before each draft:** run Job 1 (ADP). Save the final CSV block as
  `data/adp/yahoo_adp_YYYY-MM-DD.csv` using that day's date, then run `python data/import_yahoo.py` and
  restart the app. Keep old snapshots; the app diffs the newest two into a MOVE column showing risers.
- **X-Rank:** run Job 2 whenever you like. Save as `data/yahoo_xrank.csv` and import the same way.

---

## 4. During the draft — Live draft tab

Everything happens on this one screen.

1. Confirm your slot at the top.
2. As each pick happens, either use the buttons on the left (**Other team took** / **I drafted**) or tick
   **TAKEN** / **MINE** on the draft board below. Use one method per pick, not both.
3. Read the **Recommended now** list. SCORE blends value, fit for your weak categories, and positional
   scarcity. LEGAL means you can still slot him; LIKELY_GONE means he probably won't reach your next pick.
4. Use the **search bar** for a name, the **position filter** to see only centers when you need one, and the
   **Stats switch** to check projected or last-season numbers without leaving the page.
5. Watch "How many more players of each position still fit" so you don't end up unable to field a lineup.
   With two C slots, don't finish with fewer than three C-eligible players.

If you disagree with the model, raise **Trust my rankings** to 1.0 and your order wins wherever you set one.

---

## 5. During the season

- **Matchup tab:** paste both rosters, see the projected 9-cat score and which categories are close.
- **Waivers & streaming tab:** pickup scores weighted by your weak categories and by who plays 4 games this
  week. You get 4 adds per week — spend them on schedule, not on marginal talent.
- **Injuries tab:** current report joined to the rankings, for IL moves and buy-lows.
- Refresh data weekly: rerun Job 1 for ADP if you like, and `python data/schedule.py` and
  `python data/injuries.py` for the schedule and injury report.

---

## Files you'll edit

| File | What it's for |
|---|---|
| `data/my_rankings.csv` | Your ranks, tiers, notes, do-not-draft list. Usually edited in the app. |
| `data/overrides.csv` | Minutes multiplier, games played, position, team for any player you want to adjust. |
| `data/manual_projections.csv` | Full stat lines for players with no real stats (rookies, last year's injured). Rough estimates — edit freely. |
| `data/adp/` | Dated ADP snapshots. Add a new one before each draft. |
| `config.py` | League settings, if anything changes. |


---

## Updating to a new version

When you get a new `nba9cat.zip`, **don't replace your whole folder** — your rankings, league settings
and Yahoo data live inside it. Instead:

1. Unzip the new version somewhere temporary (Downloads is fine).
2. Open a terminal in that **new** folder.
3. Run, pointing at your existing copy:

```
py update.py "D:\Fantasy Basketball Tool\nba9cat"
```

It copies only program files (the app, engine, fetch scripts and guides), prints exactly what it changed,
and backs up anything it replaced into a dated `_backup` folder inside your copy. These files are never
touched:

`my_rankings.csv` · `leagues.json` · `no_stats.csv` · `overrides.csv` · `yahoo_*.csv` · `season_*.csv` ·
`schedule.csv` · `injuries.csv` · `data/adp/`

4. Delete the temporary folder, then start the app from your own folder as usual.

The `VERSION` file in the folder shows which build you're on. If an update ever goes wrong, copy the files
back out of `_backup`.
