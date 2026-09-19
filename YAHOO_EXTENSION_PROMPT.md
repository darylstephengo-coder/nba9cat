# Get Yahoo data with the Claude in Chrome extension

Open Chrome, make sure you're signed into Yahoo Fantasy, open the Claude extension side panel, and paste
everything below the line as one message. Click **Allow** when it asks for permission on yahoo.com pages.

The extension can read pages but can't run scripts or save files, so it will hand you the data as CSV text
in the chat. Copy each block into Notepad and save it with the filename shown ("Save as type: All files").
Then put both files in the app's `data/` folder, run `python data/import_yahoo.py`, and restart the app.

Replace `32830` in the prompt with your league ID if you want a different league (the ID is in the URL
when you open the league).

---

You are collecting fantasy basketball data from my Yahoo league (ID 32830), which I'm already signed into.
Read pages only: do not click Add, Drop, Trade, Edit, or anything on rosters or settings. Read the tables
through the page text or accessibility tree, not from screenshots, so values are exact. Never invent a
value: if a cell is blank on the page, leave it blank. You do not need to run any scripts or download any
files; deliver everything as CSV text in this chat.

## Task 1: Player stats and ranks

Go to:
https://basketball.fantasysports.yahoo.com/nba/32830/players?status=ALL&pos=P&cut_type=33&stat1=S_AS_2025&myteam=0&sort=AR&sdir=1&count=0

Confirm the stats selector above the table shows **Average Stats** for the **2025-26 season** (per-game
averages, not totals). If it shows totals, change it to averages. The table shows 25 players per page and
the `count=` value in the URL is the starting row: count=0, 25, 50, 75, and so on. Continue until you pass
rank 350 or the table is empty.

For every row collect these fields in this order:

PLAYER,TEAM,POS,STATUS,PRE_RANK,CUR_RANK,PCT_OWNED,GP,MIN,FGM,FGA,FG_PCT,FTM,FTA,FT_PCT,FG3M,PTS,REB,AST,STL,BLK,TOV

- POS is Yahoo's eligibility exactly as shown, e.g. PG,SG or PF,C. Wrap it in double quotes in the CSV
  because it contains commas ("PG,SG").
- PRE_RANK is the "Pre-Season" rank column; CUR_RANK is the "Current" rank column.
- Yahoo shows made/attempted as one cell like 8.5/16.2: write FGM=8.5 and FGA=16.2 (same for FTM/FTA).
- STATUS is the injury tag next to the name (INJ, GTD, O, NA) or blank.
- Rookies with no 2025-26 stats still get a row, with blank stat cells.

**Delivery:** after every 4 pages (100 players), paste the rows collected so far as a CSV code block
headed `yahoo_players.csv (rows N to M)`, then keep going. Do not wait until the end to output anything.
When finished, paste one final complete block for the whole file, with the header row as the first line.

## Task 2: Draft analysis (ADP)

Go to:
https://basketball.fantasysports.yahoo.com/nba/32830/draftanalysis?sort=DA_AP&count=0

Same paging (count=0, 25, 50 ...). Continue until the Avg Pick column is blank or you pass 350 players.
For each row collect:

PLAYER,TEAM,POS,ADP,AVG_ROUND,PCT_DRAFTED

ADP is the "Avg Pick" column. If the page has an X-Rank or expert rank column, add X_RANK as a final
column; otherwise leave it out. Deliver the same way: a code block every 4 pages, then one final
complete block headed `yahoo_adp.csv`.

## If something goes wrong

- If Yahoo shows a "slow down" or error page, wait 30 seconds and reload the same `count=` URL.
- If a page fails twice, note its `count=` value and move on; list every skipped page at the end.
- If you run low on memory or context, stop and tell me the last `count=` you finished for each task; I
  will start a new chat and ask you to resume from there.

## Finish

Report: rows in each file, the first three player names in each, and any skipped pages. Do not analyse or
summarise the players; I only need the data.
