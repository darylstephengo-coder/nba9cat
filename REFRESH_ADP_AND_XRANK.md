# Refreshing ADP, and getting X-Rank

Two jobs for the Claude in Chrome extension. Sign into Yahoo first, open the side panel, and paste one job
at a time. Click **Allow** when it asks for permission on basketball.fantasysports.yahoo.com.

The extension can read pages but cannot save files or run scripts, so it hands the data back as CSV text
in the chat. You don't need to save anything yourself: paste each block into your Claude chat and it gets
assembled and imported for you.

Replace `32830` with the league ID you're refreshing for (the number in the URL when you open that league).

---

## Job 1 — ADP refresh (run a day or two before each draft)

> You have browser tools only — that's fine. Don't save files or run anything; give me the data as CSV text
> in this chat.
>
> Go to https://basketball.fantasysports.yahoo.com/nba/32830/draftanalysis
>
> First tell me whether the "Last 7 Days" ADP column is unlocked on my account. Use it if it is, because it
> reflects the current market; otherwise use "All Drafts". Say which one you used before you start reading.
>
> Then read the table page by page using the Next arrow (30 rows per page), reading page text rather than
> screenshots so the values are exact. For each row collect:
>
> PLAYER,TEAM,POS,ADP,PCT_DRAFTED
>
> Wrap POS in double quotes since it contains commas ("PG,SG"). Ignore the Rank and Pos Rank columns — I
> already have those and don't want them.
>
> Stop when ADP goes blank. Paste the rows as a CSV code block after every 4 pages, then one final complete
> block with the header row first. If a page fails, wait 30 seconds and retry; list any skipped pages at the
> end. If you run low on context, stop and tell me the last page you finished so I can resume from there.

---

## Job 2 — X-Rank (Yahoo's Expert Rank)

X-Rank is Yahoo's experts' ranking of how they think players will finish this season. It uses default
scoring, which for basketball is the nine categories, so it matches your league. Because it also sets
autopick order, it should appear in the pre-draft rankings editor, not only the live draft room. Fantasy
Plus isn't required for it (Composite Expert Rank, which blends Yahoo analysts with Rotowire, does require
Plus).

> You have browser tools only — that's fine. Don't save files or run anything; give me the data as CSV text
> in this chat.
>
> In my Yahoo fantasy basketball league 32830, open Draft Central and find the pre-draft rankings editor —
> the page where I reorder players for autopick.
>
> This page is editable, so treat it as read-only: do not drag, reorder, delete, or save anything. If it
> ever prompts to save changes, decline.
>
> Before reading any data, tell me two things: what ranking-source options the page offers, and the exact
> column header you are about to read, word for word. I'm looking for "Expert Rank" or "X-Rank". If the page
> only offers the default league-settings rank ("Rank", "Default Rank", "Pre-Draft Rank" or similar), stop
> and tell me — do not substitute it, I already have that number.
>
> Once it's showing Expert Rank, read the list in that order and give me the top 200 as a CSV code block
> with the header PLAYER,X_RANK. Read page text, not screenshots. Paste a block every 50 rows, then one
> final complete block.

**Fallback:** if that page won't show Expert Rank, Yahoo displays X-Rank next to each player in the live
draft room. Use the same prompt on draft day, adding "I have the draft room open" and "do not click
anything in the draft room — only read." Or type the top 30 by hand into the editable X_RANK column on the
app's My rankings tab.

---

## Job 3 — Yahoo's projected stats (optional, but worth it)

Yahoo publishes its own projected per-game stats for the coming season. They account for role changes,
trades and rookies, which a projection built from last season's numbers cannot. If we can read them, the
whole board can be based on them instead.

> You have browser tools only — that's fine. Don't save files or run anything; give me the data as CSV text
> in this chat.
>
> Go to https://basketball.fantasysports.yahoo.com/nba/32830/players?status=ALL&pos=P&cut_type=33&myteam=0&sort=AR&sdir=1
>
> Above the stats table there is a dropdown that selects which stats are shown. **First, list every option
> in that dropdown for me, word for word**, and tell me whether any of them is a projection for the
> 2026-27 season (it may be called "Projected Season", "2026 Season Projections", "Preseason Projections"
> or similar). Don't read any data until you've told me.
>
> If a projection option exists: select it, confirm the table header now shows projected stats, then read
> the table page by page (25 rows per page, the `count=` value in the URL is the starting row: 0, 25, 50 …)
> for the top 300 players. For each row collect:
>
> PLAYER,GP,MIN,FGM,FGA,FG_PCT,FTM,FTA,FT_PCT,FG3M,PTS,REB,AST,STL,BLK,TOV
>
> Yahoo shows made/attempted as one cell like 8.5/16.2 — split it into FGM and FGA (same for FTM/FTA).
> Read page text, not screenshots. Post a CSV block every 4 pages and one final complete block with the
> header. Don't stop to ask; retry once after 30 seconds on failure and continue.
>
> If no projection option exists, say so and stop — don't substitute last season's stats.

Save the final block as `data/yahoo_projections.csv` and run `python data/import_yahoo.py`. A
**Projection source** control appears in the sidebar letting you switch between Yahoo's projections and the
built-in ones.

## What you end up comparing

| Column | Meaning |
|---|---|
| X_RANK | Yahoo's experts' projected finish for this season |
| ADP | Where drafters actually take him |
| MY_RANK | Your own ranking |
| X-ADP | X_RANK minus ADP. Negative = the experts rate him higher than the room drafts him |
| MY-ADP | Your rank minus ADP. Negative = you rate him higher than the room does; these are your targets |
| MOVE | ADP change since the previous snapshot; positive = rising |

## If you're importing the files yourself

Save Job 1's final block as `data/adp/yahoo_adp_YYYY-MM-DD.csv` (today's date) and Job 2's as
`data/yahoo_xrank.csv`, then run `python data/import_yahoo.py` and restart the app. The importer always
reads the newest ADP snapshot and diffs it against the previous one to build the MOVE column, so keep the
old snapshots.
