# Open the app on your phone

The app is a website, so the job is to host it somewhere your phone can reach. Three options, easiest first.

## Option A: Streamlit Community Cloud (free, works anywhere, recommended)

1. Put this folder in a GitHub repository (private is fine). Include the `data/season_*.csv` files —
   the cloud can't fetch from stats.nba.com, so the stats travel with the code.
2. Go to https://share.streamlit.io, sign in with GitHub, click "Create app", pick the repo, and set the
   main file to `app.py`. Choose a subdomain like `daryl-9cat`.
3. Two minutes later you have `https://daryl-9cat.streamlit.app`. Open it on your phone, tap Share →
   "Add to Home Screen", and it behaves like an app icon.
4. Turn on **Phone layout** at the top of the app. Panels stack vertically and tables show fewer columns.

Keeping it current: `.github/workflows/refresh.yml` pulls the schedule and injury report every morning
and commits them, so the Matchup, Waivers, and Injuries tabs update on their own. Player stats need a
local `python data/fetch_stats.py` followed by a git push (weekly in-season is plenty). Every push
redeploys automatically.

Limits to know: the free tier sleeps the app after ~12 hours without visitors (first load after that takes
about 30 seconds), and you get one private app. Make the repo private if you don't want league-mates
finding it.

## Option B: Run on your computer, open on your phone over Wi-Fi

```bash
streamlit run app.py --server.address 0.0.0.0
```

Then on your phone (same Wi-Fi) browse to `http://<your-computer-ip>:8501`. Find the IP with
`ipconfig` (Windows) or `ifconfig` (Mac). Good for draft night; useless once you leave the house.

## Option C: Computer at home, phone anywhere

Install Tailscale on both devices (free for personal use). Run the app as in Option B and browse to your
computer's Tailscale IP from the phone. Fully private, no GitHub, but the computer has to stay on.

## Yahoo integration on the cloud

Yahoo's OAuth needs a browser login on first run, so do that locally once; `yahoo/oauth2.json` is
git-ignored. If you want live Yahoo rosters on the phone, paste that file's contents into the app's
Secrets on Streamlit Cloud and load it from `st.secrets` — ask and I'll wire that up.
