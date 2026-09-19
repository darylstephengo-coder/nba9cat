"""9-Cat Command Center — draft tool and season tool.
Run:  streamlit run app.py     (Windows: py -m streamlit run app.py)
"""
import pandas as pd
import streamlit as st
import config as C
from engine import leagues as L
from engine import rankings as R
from engine.projections import (load_projection, load_seasons, with_pcts, season_totals,
                                multi_season_average, load_yahoo_projection, merge_yahoo_projection)
from engine.zscores import compute_values, category_profile
from engine.positions import positional_adjustment, open_slot_needs, parse_pos, fill_slots
from engine.minutes import project_team_minutes, apply_minutes, depth_chart
from engine.draft import Draft
from engine.planner import my_picks, plan
from engine.matchup import compare
from engine.waiver import score_free_agents, streaming_targets

st.set_page_config(page_title="9-Cat Command Center", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown("""<style>
section[data-testid="stSidebar"], div[data-testid="stSidebar"] {width: 215px !important;
    min-width: 215px !important; max-width: 215px !important;}
section[data-testid="stSidebar"] > div, div[data-testid="stSidebar"] > div {width: 215px !important;}
section[data-testid="stSidebar"] * {font-size: 0.78rem !important;}
section[data-testid="stSidebar"] h2 {font-size: 1rem !important;}
.block-container {padding-top: 1.0rem; padding-bottom: 0.5rem; padding-left: 1rem; padding-right: 1rem;
                 max-width: 100% !important; width: 100% !important;}
section.main > div {max-width: 100% !important;}
div[data-testid="stAppViewContainer"] > section:last-child {width: 100% !important;}
h1 {font-size: 1.6rem !important; margin-bottom: 0.2rem;}
h2, h3 {font-size: 1.15rem !important;}
div[data-testid="stDataFrame"] div, div[data-testid="stDataEditor"] div {font-size: 0.86rem;}
</style>""", unsafe_allow_html=True)

CATS = ["FG_PCT", "FT_PCT", "FG3M", "PTS", "REB", "AST", "STL", "BLK", "TOV"]
CAT_COLS = {c: C.CAT_LABEL[c] for c in CATS}
ZC = [f"z_{c}" for c in C.ALL_CATS]


# ----------------------------------------------------------------- data
@st.cache_data
def get_raw():
    return load_projection("data")


@st.cache_data
def get_seasons():
    return load_seasons("data")


@st.cache_data
def get_yahoo_proj():
    return load_yahoo_projection("data")


@st.cache_data(show_spinner=False)
def build(minutes_cap, avail_w, use_rot, punts_key, pool, tovw, source):
    raw = get_raw()
    pm = project_team_minutes(raw, cap=minutes_cap)
    proj = apply_minutes(pm) if use_rot else raw
    if source == "Yahoo projections":
        proj = merge_yahoo_projection(proj, get_yahoo_proj())
    else:
        proj = merge_yahoo_projection(proj, None)
    punts = list(punts_key)
    board = compute_values(proj, punts, pool, tovw, avail_weight=avail_w)
    board["POS_ADJ"] = positional_adjustment(board)
    return proj, pm, with_pcts(board)


def stat_frame(view, proj, seasons):
    """Return PLAYER + the nine categories for the chosen stats view."""
    cols = ["PLAYER", "GP", "MIN"] + CATS
    if view.startswith("Projected"):
        df = with_pcts(proj).copy()
        if "PROJ_GP" in df.columns:            # projected games, not last season's
            df["GP"] = df["PROJ_GP"].round(0)
    elif "totals" in view:
        df = season_totals(seasons[0])
    else:
        df = with_pcts(seasons[0])
    return df[[c for c in cols if c in df.columns]]


NO_STATS_COLS = ["GP", "MIN"] + CATS


def merge_stats(base, view, proj, seasons):
    """Attach the chosen stats view. Players with no real stats get blank cells, never estimates."""
    sf = stat_frame(view, proj, seasons)
    base = base.drop(columns=[c for c in sf.columns if c != "PLAYER" and c in base.columns])
    out = base.merge(sf, on="PLAYER", how="left")
    flags = proj.set_index("PLAYER")
    if "NO_STATS" in flags.columns:
        blank = out["PLAYER"].map(flags["NO_STATS"]).fillna(False).astype(bool)
        num = [c for c in NO_STATS_COLS if c in out.columns]
        for c in num:                       # nullable float so blanks render cleanly
            out[c] = pd.to_numeric(out[c], errors="coerce").astype("Float64")
        out.loc[blank, num] = pd.NA
        out["DATA"] = out["PLAYER"].map(flags["STATUS"]).fillna("")
        out.loc[blank & (out["DATA"] == ""), "DATA"] = ""
    return out


def pretty(df):
    return df.rename(columns=CAT_COLS)


# ----------------------------------------------------------------- sidebar
if "leagues" not in st.session_state:
    st.session_state.leagues = L.load()
if "my_ranks" not in st.session_state:
    st.session_state.my_ranks = R.load()

with st.sidebar:
    st.header("Setup")
    names = [lg["name"] for lg in st.session_state.leagues]
    chosen = st.selectbox("League", names, key="league_name")
    idx = names.index(chosen) if chosen in names else 0
    league = st.session_state.leagues[idx]
    L.activate(league)
    st.caption(L.describe(league))

    mode = st.radio("Tool", ["Draft tool", "Season tool", "League settings"], key="mode")

    strategy = st.selectbox("Strategy", list(C.PUNT_PRESETS),
                            index=list(C.PUNT_PRESETS).index(league.get("strategy", "Balanced"))
                            if league.get("strategy") in C.PUNT_PRESETS else 0,
                            help="Balanced values all nine categories. A punt drops one or two and "
                                 "re-ranks everyone, which changes the board a lot.")
    if st.session_state.get("_last_strategy") != strategy:
        st.session_state["punt_sel"] = list(C.PUNT_PRESETS[strategy])
        st.session_state["_last_strategy"] = strategy
    punts = st.multiselect("Punt categories", C.ALL_CATS, key="punt_sel",
                           format_func=lambda c: C.CAT_LABEL[c],
                           help="Categories you're giving up on. Players who only help there drop down the board.")
    draft_slot = st.number_input("My draft pick number", 1, C.TEAMS, int(league.get("draft_slot", 1)),
                                 help="Which pick you have in round 1.")
    if draft_slot != league.get("draft_slot") or strategy != league.get("strategy"):
        league["draft_slot"], league["strategy"] = int(draft_slot), strategy
        L.save(st.session_state.leagues)

    yp_available = get_yahoo_proj() is not None
    st.session_state["_yp"] = yp_available
    source = st.radio("Projection source", ["Yahoo projections", "Last season, minutes-adjusted"],
                      index=0 if yp_available else 1, key="proj_source",
                      help="Yahoo/Rotowire's own projections for this season. The other option is last "
                           "season's stats rescaled to projected minutes — for players whose minutes don't "
                           "change, that is simply last season's line.",
                      disabled=not yp_available)
    if not yp_available:
        st.caption("Yahoo projections not loaded — see REFRESH_ADP_AND_XRANK.md")

    with st.expander("Advanced settings"):
        use_rot = st.toggle("Project minutes to 240 per team", value=True,
                            help="Rescales each player's stats to the minutes his team can actually give him. "
                                 "Leave on.")
        minutes_cap = st.slider("Max minutes per player", 30.0, 40.0, 36.0, 0.5)
        avail_w = st.slider("Penalty for missed games", 0.0, 1.0, 0.5, 0.1,
                            help="0 = judge players per game. 1 = punish injury-prone players hard.")
        pool = st.slider("Reference pool", 120, 300, C.POOL_SIZE, 8,
                         help="How many players count as 'average'. Default is everyone rostered in your league.")
        tovw = st.slider("Turnover weight", 0.0, 1.0, C.TOV_WEIGHT, 0.05)
        st.caption("Players with no stats are ranked from the market, then pushed down:")
        inj_disc = st.slider("Coming back from a lost season", 0.0, 0.6, C.INJ_DISCOUNT, 0.05,
                             help="0.20 means a player the market ranks 20th is treated as roughly 24th.")
        rookie_disc = st.slider("Rookie", 0.0, 0.8, C.ROOKIE_DISCOUNT, 0.05,
                                help="Rookies usually cost you FG%, FT% and turnovers in 9-cat.")
        phone = st.toggle("Phone layout", value=False)

proj, pm, board = build(minutes_cap, avail_w, use_rot, tuple(punts), pool, tovw, source)
board = R.blend(board, st.session_state.my_ranks, 0.0, "AVAIL_VALUE")
board = R.rank_with_no_stats(board, inj_disc, rookie_disc)
seasons = get_seasons()
last_label = str(seasons[0]["SEASON"].iloc[0]) if seasons else "last season"
PROJ_LABEL = ("Projected (Yahoo)" if (source == "Yahoo projections" and st.session_state.get("_yp"))
              else "Last season, minutes-adjusted")
STAT_VIEWS = [PROJ_LABEL, f"{last_label} per game", f"{last_label} totals"]
DEFAULT_VIEW = 0


def cols(spec):
    n = spec if isinstance(spec, int) else len(spec)
    return [st.container() for _ in range(n)] if phone else st.columns(spec)


# ================================================================= DRAFT TOOL
if mode == "Draft tool":
    st.title("Draft tool")
    with st.expander("How to use this", expanded=False):
        st.markdown("""
**Board** — every player, sorted by your ranking. Blank stat cells mean no real 2025-26 numbers
exist: *DATA = INJ* is a returning player who missed last season, blank is a player with no NBA
record yet. Nothing is made up for them — instead they're ranked from the market (Yahoo X-Rank and
ADP) and pushed down, more for rookies than for a returning veteran. *BASIS* tells you which route
each player's MY_VALUE took. Adjust the two discounts in Advanced settings. Three reference numbers:
*ADP* is where people actually draft him, *XRANK* is Yahoo's experts' opinion, *MY_RANK* is yours.
Tick **TAKEN** when anyone drafts a player and **MINE** when you do.

**My rankings** — type your own rank for players you feel strongly about. Blank is fine; the model fills the gaps.

**By position** — the best players still available at each position, five columns side by side.

**Plan** — your pick numbers and who should still be available at each.

**Compare** — put 2 to 4 players side by side.
""")
    if "draft" not in st.session_state:
        st.session_state.draft = Draft(proj, int(draft_slot), punts)
    d: Draft = st.session_state.draft
    d.my_slot = int(draft_slot)
    if d.punts != list(punts) or d.avail_weight != avail_w:
        d.punts, d.avail_weight = list(punts), avail_w
        d.refresh()
    d.set_my_ranks(st.session_state.my_ranks, 1.0)

    page = st.radio("Page", ["Board", "By position", "My rankings", "Draft results", "Player pool",
                             "Plan", "Compare"], horizontal=True, key="draft_page",
                    label_visibility="collapsed")

    # ---- Board -------------------------------------------------------
    if page == "Board":
        c1, c2, c3, c4 = st.columns([1, 1, 1, 3])
        c1.metric("Pick on the clock", d.pick_number)
        c2.metric("Picks until yours", d.picks_until_mine())
        c3.metric("I've drafted", len(d.mine))
        with c4:
            st.caption("Quick entry — type part of a name and press Enter")
            with st.form("quick_pick", clear_on_submit=True, border=False):
                qa, qb, qc = st.columns([4, 1, 1])
                typed = qa.text_input("Player taken", key="quick_text", label_visibility="collapsed",
                                      placeholder="e.g. jok, wemby, sga…")
                mine_flag = qb.checkbox("Mine", key="quick_mine")
                go = qc.form_submit_button("Mark", type="primary", width="stretch")
            if go and typed.strip():
                hits = d.find(typed)
                if not hits:
                    st.warning(f"No available player matches '{typed}'.")
                elif len(hits) == 1 or hits[0][0] < hits[1][0]:
                    name = hits[0][2]
                    d.set_status(name, True, bool(mine_flag))
                    st.session_state["last_pick_msg"] = f"{'You drafted' if mine_flag else 'Taken'}: {name}"
                    st.rerun()
                else:
                    st.session_state["quick_options"] = [h[2] for h in hits]
                    st.session_state["quick_mine_pending"] = bool(mine_flag)

        if st.session_state.get("quick_options"):
            st.warning("Several matches — pick one:")
            opt_cols = st.columns(min(6, len(st.session_state["quick_options"])))
            for i, nm in enumerate(st.session_state["quick_options"][:6]):
                if opt_cols[i].button(nm, key=f"qopt_{nm}", width="stretch"):
                    d.set_status(nm, True, st.session_state.get("quick_mine_pending", False))
                    st.session_state["quick_options"] = None
                    st.session_state["last_pick_msg"] = f"Taken: {nm}"
                    st.rerun()
            if st.button("Cancel", key="qcancel"):
                st.session_state["quick_options"] = None; st.rerun()

        with st.expander("Mark several picks at once"):
            st.caption("Useful when you look away and miss a few. Tick the players, then press the button. "
                       "Type to filter the list.")
            st.session_state.setdefault("bulk_round", 0)
            bulk = st.multiselect("Players", d.available()["PLAYER"].tolist(),
                                  key=f"bulk_names_{st.session_state.bulk_round}",
                                  placeholder="start typing a name…")
            k1, k2, k3 = st.columns([1, 1, 3])
            if k1.button("Mark taken", key="bulk_taken", type="primary",
                         disabled=not bulk, width="stretch"):
                for nm in bulk:
                    d.set_status(nm, True, False)
                st.session_state.bulk_round += 1        # fresh widget = cleared selection
                st.session_state["last_pick_msg"] = f"Marked {len(bulk)} players taken"
                st.rerun()
            if k2.button("These are mine", key="bulk_mine", disabled=not bulk, width="stretch"):
                for nm in bulk:
                    d.set_status(nm, True, True)
                st.session_state.bulk_round += 1
                st.session_state["last_pick_msg"] = f"Added {len(bulk)} players to my roster"
                st.rerun()

        if st.session_state.get("last_pick_msg"):
            u1, u2 = st.columns([5, 1])
            u1.success(st.session_state["last_pick_msg"])
            if u2.button("Undo", key="quick_undo", width="stretch"):
                d.undo()
                st.session_state["last_pick_msg"] = None
                st.rerun()

        SORTABLE = ["MY_VALUE", "ADP", "X_RANK", "MY_RANK"] + CATS + ["GP"]
        f1, f2, f3, f4, f5, f6 = cols([3, 2, 2, 3, 2, 2])
        q = f1.text_input("Search", key="b_q", placeholder="player name")
        pos_f = f2.selectbox("Position", ["All"] + list(C.ROSTER_SLOTS), key="b_pos")
        sort_by = f3.selectbox("Sort by", SORTABLE, key="b_sort", format_func=lambda c: C.CAT_LABEL.get(c, c))
        view = f4.selectbox("Stats", STAT_VIEWS, index=DEFAULT_VIEW, key="b_view")
        desc = f5.checkbox("High→low", value=sort_by in CATS, key="b_desc")
        hide_taken = f6.checkbox("Hide drafted", True, key="b_hide")
        tick_mode = st.radio("Tick behaviour", ["One at a time", "Tick several, then confirm"],
                             horizontal=True, key="b_tickmode",
                             help="One at a time: each tick is applied immediately. "
                                  "Tick several: nothing is applied until you press Confirm, so "
                                  "you can tick a whole round at once.")
        n_rows = st.slider("Rows shown", 25, 400, 100, 25, key="b_rows")

        tbl = board[~board["AVOID"]].copy()
        tbl["TAKEN"] = tbl["PLAYER"].isin(d.taken)
        tbl["MINE"] = tbl["PLAYER"].isin(d.mine)
        if hide_taken:
            tbl = tbl[~tbl["TAKEN"]]
        if q:
            tbl = tbl[tbl["PLAYER"].str.contains(q, case=False, na=False)]
        if pos_f != "All":
            tbl = tbl[tbl["POS"].apply(lambda p: bool(parse_pos(p) & C.SLOT_ELIGIBILITY[pos_f]))]
        tbl = merge_stats(tbl, view, proj, seasons)
        tbl["PLAYER_CELL"] = tbl["PLAYER"] + "  ·  " + tbl["POS"].fillna("") + " · " + tbl["TEAM"].fillna("")

        lead = ["TAKEN", "MINE", "PLAYER_CELL", "ADP", "X_RANK", "MY_RANK", "MY_VALUE"]
        if phone:
            lead = ["TAKEN", "MINE", "PLAYER_CELL", "ADP", "X_RANK", "MY_RANK"]
        show = [c for c in lead if c in tbl.columns] + CATS + ["GP"]
        tbl = tbl.sort_values(sort_by, ascending=not desc, na_position="last")   # sort the whole pool first
        grid = pretty(tbl[show].head(n_rows).round(2))
        st.caption(f"Sorted by {C.CAT_LABEL.get(sort_by, sort_by)}, "
                   f"{'high to low' if desc else 'low to high'}, across all {len(tbl)} players — then the "
                   f"top {min(n_rows, len(tbl))} shown. Players with no value for that column go last. "
                   "Use this dropdown rather than clicking a column header: the header only reorders the rows "
                   "already on screen and puts blanks first.")
        st.session_state.setdefault("board_round", 0)
        edited = st.data_editor(
            grid, hide_index=True, width="stretch", height=620,
            key=f"board_editor_{st.session_state.board_round}",
            disabled=[c for c in grid.columns if c not in ("TAKEN", "MINE")],
            column_config={"TAKEN": st.column_config.CheckboxColumn("✓", help="Drafted by anyone", width="small"),
                           "MINE": st.column_config.CheckboxColumn("ME", help="Drafted by me", width="small"),
                           "PLAYER_CELL": st.column_config.TextColumn("PLAYER", width="medium"),
                           "MY_VALUE": st.column_config.NumberColumn("MY_VALUE", width="small",
                               help="This tool's rank for your league and strategy")})
        names_in_grid = tbl["PLAYER"].head(n_rows).tolist()
        changes = [(names_in_grid[i], bool(a["TAKEN"]), bool(a["MINE"]))
                   for i, ((_, b4), (_, a)) in enumerate(zip(grid.iterrows(), edited.iterrows()))
                   if bool(b4["TAKEN"]) != bool(a["TAKEN"]) or bool(b4["MINE"]) != bool(a["MINE"])]

        if tick_mode.startswith("One"):
            # apply straight away, then give the grid a fresh identity so the tick isn't
            # replayed onto whoever moves up into that row
            if changes:
                for nm, taken, mine_f in changes:
                    d.set_status(nm, taken, mine_f)
                st.session_state["last_pick_msg"] = (
                    f"{'Added to my roster' if changes[0][2] else 'Taken'}: {changes[0][0]}"
                    if len(changes) == 1 else f"Applied {len(changes)} changes")
                st.session_state.board_round += 1
                st.rerun()
        else:
            # Nothing is applied and nothing is re-rendered until you press Confirm, so you can
            # tick as many as you like. The grid keeps your ticks on its own.
            staged = [(nm, mine_f) for nm, taken, mine_f in changes if taken or mine_f]
            if staged:
                st.info("Ticked, not yet applied: " + " · ".join(
                    f"{nm}{' (mine)' if m else ''}" for nm, m in staged))
            p1, p2, _ = st.columns([1, 1, 4])
            if p1.button(f"Confirm {len(staged)} drafted" if staged else "Confirm",
                         type="primary", key="pend_ok", width="stretch", disabled=not staged):
                for nm, mine_f in staged:
                    d.set_status(nm, True, mine_f)
                st.session_state["last_pick_msg"] = f"Confirmed {len(staged)} picks"
                st.session_state.board_round += 1
                st.rerun()
            if p2.button("Clear ticks", key="pend_clear", width="stretch", disabled=not staged):
                st.session_state.board_round += 1
                st.rerun()

        st.divider()
        b1, b2 = cols([2, 1])
        with b1:
            st.subheader("Best picks for you right now")
            st.caption("Blends value, the categories your roster is short on, and position scarcity. "
                       "LIKELY_GONE means he probably won't last until your next pick.")
            rec = d.recommend(12)
            keep = ["PLAYER", "POS", "ADP", "X_RANK", "MY_RANK", "SCORE", "LEGAL", "LIKELY_GONE", "NOTE"]
            st.dataframe(rec[[c for c in keep if c in rec.columns]], hide_index=True, width="stretch")
        with b2:
            st.subheader(f"My roster ({len(d.mine)}/{C.ROSTER_SIZE})")
            mine = board[board["PLAYER"].isin(d.mine)]
            slots = fill_slots([parse_pos(p) for p in mine["POS"]], list(mine["PLAYER"]))
            rows_html = []
            for slot, who in slots:
                if who:
                    rows_html.append(
                        f"<div style='display:flex;gap:8px;align-items:center;padding:3px 0;'>"
                        f"<span style='display:inline-block;min-width:44px;text-align:center;"
                        f"background:#f28c28;color:#111;border-radius:4px;font-size:0.72rem;"
                        f"font-weight:700;padding:2px 4px;'>{slot}</span>"
                        f"<span style='font-size:0.88rem;'>{who}</span></div>")
                else:
                    rows_html.append(
                        f"<div style='display:flex;gap:8px;align-items:center;padding:3px 0;opacity:0.45;'>"
                        f"<span style='display:inline-block;min-width:44px;text-align:center;"
                        f"border:1px solid #666;border-radius:4px;font-size:0.72rem;padding:2px 4px;'>{slot}</span>"
                        f"<span style='font-size:0.88rem;font-style:italic;'>empty</span></div>")
            st.markdown("".join(rows_html), unsafe_allow_html=True)
            if len(mine):
                st.caption("Category strengths (above 0 = helping you)")
                st.bar_chart(d.team_summary().rename(index=C.CAT_LABEL))
            if st.button("Reset draft"):
                st.session_state.draft = Draft(proj, int(draft_slot), punts); st.rerun()

    # ---- By position -------------------------------------------------
    elif page == "By position":
        st.caption("Best players still on the board at each position, under your current strategy. "
                   "Players you've marked TAKEN or AVOID are removed automatically.")
        p1, p2, p3 = cols([1, 1, 2])
        depth = p1.slider("Players per column", 5, 40, 12, key="pos_depth")
        mine_only = p2.checkbox("Hide drafted", True, key="pos_hide")
        extra = p3.multiselect("Columns to show (pick up to 2)", ["MY_VALUE", "ADP", "X_RANK", "MY_RANK"],
                               default=["MY_VALUE", "ADP"], max_selections=2, key="pos_extra")
        if not extra:
            extra = ["MY_VALUE"]

        avail = board[~board["AVOID"]].copy()
        if mine_only:
            avail = avail[~avail["PLAYER"].isin(d.taken)]
        cols_pos = st.columns(1 if phone else len(C.BASE_POS))
        for i, p in enumerate(C.BASE_POS):
            col = cols_pos[0] if phone else cols_pos[i]
            elig = avail[avail["POS"].apply(lambda x: p in parse_pos(x))].sort_values(extra[0],
                         na_position="last").head(depth)
            n_left = int((avail["POS"].apply(lambda x: p in parse_pos(x))).sum())
            col.markdown(f"**{p}** · {n_left} left")

            def short(name):
                parts = str(name).split()
                return f"{parts[0][0]}. {' '.join(parts[1:])}" if len(parts) > 1 else str(name)

            head = "".join(f"<th style='text-align:right;padding:0 0 3px 6px;font-size:0.68rem;"
                           f"opacity:.6;font-weight:600;'>{c.replace('_RANK','RANK')}</th>" for c in extra)
            body = []
            for _, r in elig.iterrows():
                cells = "".join(
                    f"<td style='text-align:right;padding:2px 0 2px 6px;font-size:0.78rem;"
                    f"opacity:.85;font-variant-numeric:tabular-nums;'>"
                    f"{'—' if pd.isna(r[c]) else format(r[c], '.0f')}</td>" for c in extra)
                body.append(
                    f"<tr style='border-bottom:1px solid rgba(128,128,128,.15);'>"
                    f"<td style='font-size:0.8rem;padding:2px 0;white-space:nowrap;overflow:hidden;"
                    f"text-overflow:ellipsis;max-width:120px;'>{short(r['PLAYER'])}</td>{cells}</tr>")
            col.markdown(
                f"<table style='width:100%;border-collapse:collapse;table-layout:fixed;'>"
                f"<thead><tr><th style='text-align:left;padding:0 0 3px 0;font-size:0.68rem;opacity:.6;"
                f"font-weight:600;'>PLAYER</th>{head}</tr></thead><tbody>"
                + "".join(body) + "</tbody></table>", unsafe_allow_html=True)

        st.divider()
        st.subheader("How thin is each position?")
        st.caption(
            "**still available** — players left on the board eligible there.  \n"
            "**above replacement** — how many of those are genuinely worth a roster spot rather than filler. "
            "This is the number to watch: when it drops toward zero, that position is running dry and you "
            "should draft it sooner.")
        rows = []
        for p, n in C.POSITION_SLOTS.items():
            e = avail[avail["POS"].apply(lambda x: p in parse_pos(x))]
            rows.append({"POS": p, "still available": len(e),
                         "above replacement": int((e["AVAIL_VALUE"] > 0).sum())})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    # ---- My rankings -------------------------------------------------
    elif page == "My rankings":
        mr = st.session_state.my_ranks
        if "my_order" not in st.session_state:
            st.session_state.my_order = (mr[mr["MY_RANK"].notna()].sort_values("MY_RANK")["PLAYER"].tolist())
        order_list = st.session_state.my_order

        st.caption("Left: the players available to rank. Right: your ranking, in order. "
                   "Once a player is on the right, he disappears from the left.")
        left, right = st.columns([1, 1]) if not phone else (st.container(), st.container())

        with left:
            st.subheader("Draft pool")
            lc1, lc2 = st.columns(2)
            lq = lc1.text_input("Search", key="mr_q")
            lpos = lc2.selectbox("Position", ["All"] + C.BASE_POS, key="mr_pos")
            lsort = st.radio("Sort pool by", ["MY_VALUE", "ADP", "X_RANK"], horizontal=True, key="mr_sort")
            pool = board[~board["AVOID"] & ~board["PLAYER"].isin(order_list)].sort_values(
                lsort, na_position="last")
            if lq:
                pool = pool[pool["PLAYER"].str.contains(lq, case=False, na=False)]
            if lpos != "All":
                pool = pool[pool["POS"].apply(lambda x: lpos in parse_pos(x))]
            PAGE = 50
            n_pages = max(1, -(-len(pool) // PAGE))
            st.session_state.setdefault("pool_page", 0)
            if st.session_state.pool_page >= n_pages:
                st.session_state.pool_page = 0
            pg = st.session_state.pool_page
            nav1, nav2, nav3 = st.columns([1, 2, 1])
            if nav1.button("◀ Prev", key="pool_prev", disabled=(pg == 0), width="stretch"):
                st.session_state.pool_page -= 1; st.rerun()
            nav2.markdown(f"<div style='text-align:center;padding-top:6px;font-size:0.85rem;'>"
                          f"{len(pool)} available · page {pg + 1} of {n_pages}</div>",
                          unsafe_allow_html=True)
            if nav3.button("Next ▶", key="pool_next", disabled=(pg >= n_pages - 1), width="stretch"):
                st.session_state.pool_page += 1; st.rerun()
            for _, row in pool.iloc[pg * PAGE:(pg + 1) * PAGE].iterrows():
                b1, b2 = st.columns([5, 1])
                adp_txt = "—" if pd.isna(row["ADP"]) else f"{row['ADP']:.0f}"
                xr_txt = "—" if pd.isna(row["X_RANK"]) else f"{row['X_RANK']:.0f}"
                b1.write(f"**{row['PLAYER']}** · {row['POS']}  \n"
                         f"<span style='opacity:.65;font-size:0.8rem'>MY_VALUE {int(row['MY_VALUE'])} · "
                         f"ADP {adp_txt} · XRANK {xr_txt}</span>", unsafe_allow_html=True)
                if b2.button("→", key=f"add_{row['PLAYER']}", help="Add to my ranking"):
                    st.session_state.my_order = order_list + [row["PLAYER"]]
                    st.rerun()


        with right:
            st.subheader(f"My ranking ({len(order_list)})")
            if not order_list:
                st.info("Press → on a player to add him. The first one you add is your #1.")
            RPAGE = 50
            r_pages = max(1, -(-len(order_list) // RPAGE))
            st.session_state.setdefault("rank_page", 0)
            if st.session_state.rank_page >= r_pages:
                st.session_state.rank_page = r_pages - 1
            rpg = st.session_state.rank_page
            if len(order_list) > RPAGE:
                rn1, rn2, rn3 = st.columns([1, 2, 1])
                if rn1.button("◀ Prev", key="rank_prev", disabled=(rpg == 0), width="stretch"):
                    st.session_state.rank_page -= 1; st.rerun()
                rn2.markdown(f"<div style='text-align:center;padding-top:6px;font-size:0.85rem;'>"
                             f"ranks {rpg * RPAGE + 1}–{min((rpg + 1) * RPAGE, len(order_list))} "
                             f"of {len(order_list)}</div>", unsafe_allow_html=True)
                if rn3.button("Next ▶", key="rank_next", disabled=(rpg >= r_pages - 1), width="stretch"):
                    st.session_state.rank_page += 1; st.rerun()
            for i in range(rpg * RPAGE, min((rpg + 1) * RPAGE, len(order_list))):
                name = order_list[i]
                row = board[board["PLAYER"] == name]
                pos = row["POS"].iloc[0] if len(row) else ""
                if len(row):
                    r0 = row.iloc[0]
                    mv = "" if pd.isna(r0["MY_VALUE"]) else f"{int(r0['MY_VALUE'])}"
                    ad = "—" if pd.isna(r0["ADP"]) else f"{r0['ADP']:.0f}"
                    xr = "—" if pd.isna(r0["X_RANK"]) else f"{r0['X_RANK']:.0f}"
                    nums = f"MY_VALUE {mv} · ADP {ad} · XRANK {xr}"
                else:
                    nums = ""
                c1, c2, c3, c4 = st.columns([5, 1, 1, 1])
                c1.write(f"**{i + 1}. {name}** · {pos}  \n"
                         f"<span style='opacity:.65;font-size:0.8rem'>{nums}</span>",
                         unsafe_allow_html=True)
                if c2.button("▲", key=f"up_{name}", disabled=(i == 0)):
                    o = list(order_list); o[i - 1], o[i] = o[i], o[i - 1]
                    st.session_state.my_order = o; st.rerun()
                if c3.button("▼", key=f"dn_{name}", disabled=(i == len(order_list) - 1)):
                    o = list(order_list); o[i + 1], o[i] = o[i], o[i + 1]
                    st.session_state.my_order = o; st.rerun()
                if c4.button("✕", key=f"del_{name}"):
                    st.session_state.my_order = [n for n in order_list if n != name]; st.rerun()

            if order_list:
                st.divider()
                st.write("**Move a player to a specific spot**")
                m1, m2, m3 = st.columns([3, 1, 1])
                who = m1.selectbox("Player", order_list, key="mv_who", label_visibility="collapsed")
                to = m2.number_input("to", 1, len(order_list), 1, key="mv_to", label_visibility="collapsed")
                if m3.button("Move", key="mv_go"):
                    o = [n for n in order_list if n != who]
                    o.insert(int(to) - 1, who)
                    st.session_state.my_order = o; st.rerun()

        st.divider()
        s1, s2, s3 = cols(3)
        if s1.button("Save my ranking", type="primary", key="mr_save"):
            m = st.session_state.my_ranks.copy()
            m["MY_RANK"] = pd.NA
            for i, n in enumerate(st.session_state.my_order, start=1):
                if n in set(m["PLAYER"]):
                    m.loc[m["PLAYER"] == n, "MY_RANK"] = i
                else:
                    m = pd.concat([m, pd.DataFrame([{"PLAYER": n, "MY_RANK": i, "AVOID": False, "NOTE": ""}])],
                                  ignore_index=True)
            st.session_state.my_ranks = m
            R.save(m); st.cache_data.clear()
            st.success(f"Saved {len(st.session_state.my_order)} ranked players.")
        if s2.button("Clear my ranking", key="mr_clear"):
            st.session_state.my_order = []; st.rerun()
        s3.download_button("Download CSV", st.session_state.my_ranks.to_csv(index=False),
                           file_name="my_rankings.csv")

    # ---- Draft results -----------------------------------------------
    elif page == "Draft results":
        st.caption("Everyone drafted so far, newest first. Press ✕ to put a player back in the pool "
                   "if you ticked the wrong name.")
        if not d.taken:
            st.info("Nobody drafted yet. Tick TAKEN or MINE on the Board as picks happen.")
        else:
            r1, r2 = cols(2)
            with r1:
                st.subheader(f"My team ({len(d.mine)})")
                for name in reversed(d.mine):
                    row = board[board.PLAYER == name]
                    pos = row["POS"].iloc[0] if len(row) else ""
                    c_a, c_b = st.columns([5, 1])
                    c_a.write(f"**{name}**  ·  {pos}")
                    if c_b.button("✕", key=f"rm_mine_{name}"):
                        d.set_status(name, False, False); st.rerun()
            with r2:
                st.subheader(f"Taken by others ({len(d.taken) - len(d.mine)})")
                for name in reversed([p for p in d.taken if p not in d.mine]):
                    c_a, c_b = st.columns([5, 1])
                    c_a.write(name)
                    if c_b.button("✕", key=f"rm_tk_{name}"):
                        d.set_status(name, False, False); st.rerun()
            st.divider()
            st.write("**Pick order**")
            order = pd.DataFrame({"#": range(1, len(d.taken) + 1), "PLAYER": d.taken})
            order["WHO"] = order["PLAYER"].apply(lambda p: "ME" if p in d.mine else "")
            st.dataframe(order, hide_index=True, width="stretch", height=320)
            if st.button("Clear the whole draft"):
                st.session_state.draft = Draft(proj, int(draft_slot), punts); st.rerun()

    # ---- Player pool -------------------------------------------------
    elif page == "Player pool":
        st.caption("Tick REMOVE for anyone you will never draft. They disappear from the Board, By position, "
                   "recommendations and the Plan. Untick to bring them back. All 400 players stay in the file.")
        mr = st.session_state.my_ranks
        removed_now = set(mr[mr["AVOID"].fillna(False).astype(bool)]["PLAYER"])
        c_m1, c_m2 = cols(2)
        c_m1.metric("In the pool", len(board) - len(removed_now))
        c_m2.metric("Removed", len(removed_now))

        f_a, f_b, f_c = cols([2, 2, 1])
        q_pool = f_a.text_input("Search (optional)", key="pool_q")
        rng = f_b.slider("Show ranks", 1, int(board["MY_VALUE"].max()),
                         (1, int(board["MY_VALUE"].max())), key="pool_rng")
        only_removed = f_c.checkbox("Removed only", key="pool_only")

        pool_tbl = board[["PLAYER", "TEAM", "POS", "MY_VALUE", "ADP", "X_RANK", "AVOID"]].copy()
        pool_tbl = pool_tbl.rename(columns={"AVOID": "REMOVE"})
        pool_tbl = pool_tbl[(pool_tbl["MY_VALUE"] >= rng[0]) & (pool_tbl["MY_VALUE"] <= rng[1])]
        if q_pool:
            pool_tbl = pool_tbl[pool_tbl["PLAYER"].str.contains(q_pool, case=False, na=False)]
        if only_removed:
            pool_tbl = pool_tbl[pool_tbl["REMOVE"]]
        pool_tbl = pool_tbl.sort_values("MY_VALUE")
        st.write(f"Showing {len(pool_tbl)} players.")
        st.session_state.setdefault("pool_round", 0)
        ed_pool = st.data_editor(
            pool_tbl, hide_index=True, width="stretch", height=620,
            key=f"pool_editor_{st.session_state.pool_round}",
            disabled=[c for c in pool_tbl.columns if c != "REMOVE"],
            column_config={"REMOVE": st.column_config.CheckboxColumn("REMOVE", width="small"),
                           "MY_VALUE": st.column_config.NumberColumn("MY_VALUE", width="small")})
        if st.button("Save removals", type="primary", key="pool_save"):
            m = st.session_state.my_ranks
            for _, row in ed_pool.iterrows():
                want = bool(row["REMOVE"])
                if want != (row["PLAYER"] in removed_now):
                    m = R.set_avoid(m, row["PLAYER"], want)
            st.session_state.my_ranks = m
            st.session_state.pool_round += 1
            R.save(m); st.cache_data.clear(); st.rerun()
        if removed_now:
            with st.expander(f"Currently removed ({len(removed_now)})"):
                st.write(" · ".join(sorted(removed_now)))

    # ---- Plan --------------------------------------------------------
    elif page == "Plan":
        st.info(f"You pick {int(draft_slot)} of {C.TEAMS} in a snake draft, so your picks come in pairs. "
                "For each of your 13 picks, this shows who is usually still on the board at that point — "
                "so you can plan which round to take each position instead of improvising.")
        st.caption(
            "**USUALLY DRAFTED AT** — the pick number where other people normally take him.  \n"
            "**MY_VALUE** — where this tool ranks him for your league.  \n"
            "**VALUE GAINED** — the difference. 16 means you're getting a player worth a 4th-overall pick at "
            "pick 20, so you gain 16 places of value. A negative number means you'd be reaching for him.")
        reach = st.slider("How far ahead of ADP I'll reach", 0, 15, 6, key="p_reach")
        picks = my_picks(int(draft_slot))
        st.markdown("**Your picks:** " + " · ".join(f"R{i+1} #{p}" for i, p in enumerate(picks)))
        pl = plan(board, int(draft_slot), reach=reach)
        for rnd, g in pl.groupby("ROUND"):
            with st.expander(f"Round {rnd} — pick #{int(g['PICK'].iloc[0])}", expanded=(rnd <= 3)):
                gg = g[["PLAYER", "POS", "MARKET", "MODEL_RANK", "EDGE"]].rename(columns={
                    "MARKET": "USUALLY DRAFTED AT", "MODEL_RANK": "MY_VALUE", "EDGE": "VALUE GAINED"})
                st.dataframe(gg, hide_index=True, width="stretch")
        st.caption("MARKET = where he usually goes. EDGE above 0 means he's a bargain at that pick.")

    # ---- Compare -----------------------------------------------------
    elif page == "Compare":
        picks_c = st.multiselect("Players (2-4)", sorted(proj["PLAYER"]),
                                 default=list(board.sort_values("MY_VALUE")["PLAYER"].head(2)),
                                 max_selections=4, key="c_names")
        cv = st.radio("Stats to show", STAT_VIEWS, index=DEFAULT_VIEW, key="c_view", horizontal=not phone)
        if len(picks_c) >= 2:
            src = merge_stats(board[["PLAYER", "TEAM", "POS", "ADP", "X_RANK", "MY_RANK", "MY_VALUE"]].copy(),
                              cv, proj, seasons)
            d2 = src[src["PLAYER"].isin(picks_c)].set_index("PLAYER").reindex(picks_c)
            rows = ["ADP", "X_RANK", "MY_RANK", "MY_VALUE"] + CATS + ["GP", "MIN"]
            t = d2[[r for r in rows if r in d2.columns]].T
            t.index = [C.CAT_LABEL.get(i, i) for i in t.index]
            lower = {"TO", "ADP", "X_RANK", "MY_RANK", "MY_VALUE"}

            def hl(row):
                v = pd.to_numeric(row, errors="coerce")
                if row.name == "DATA":
                    return [""] * len(row)
                if v.notna().sum() < 2:
                    return [""] * len(row)
                best = v.idxmin() if row.name in lower else v.idxmax()
                return ["background-color: rgba(242,140,40,0.35); font-weight:600" if c == best else ""
                        for c in row.index]
            def fmt(v):
                if v is None or (not isinstance(v, str) and pd.isna(v)):
                    return ""
                return v if isinstance(v, str) else f"{v:,.2f}"

            st.dataframe(t.style.apply(hl, axis=1).format(fmt),
                         width="stretch", height=min(60 + 36 * len(t), 700))
            st.caption("Highlight = best in that row (lowest for TO, ADP and the rank columns).")
            z = board[board["PLAYER"].isin(picks_c)].set_index("PLAYER")[ZC].reindex(picks_c).T
            z.index = [C.CAT_LABEL[c.replace("z_", "")] for c in z.index]
            st.bar_chart(z)

# ================================================================= SEASON TOOL
elif mode == "Season tool":
    st.title("Season tool")
    with st.expander("How to use this", expanded=False):
        st.markdown("""
**My team** — paste your roster to see which categories you win and lose.
**This week** — paste both rosters to project the matchup.
**Waivers** — who to pick up, weighted by your weak categories and by who plays most games this week.
**Injuries** and **Rotations** — current injury report, and who gets the minutes on every NBA team.
""")
    spage = st.radio("Page", ["My team", "This week", "Waivers", "Injuries", "Rotations", "All players"],
                     horizontal=True, key="season_page", label_visibility="collapsed")

    def games_this_week():
        try:
            import datetime as dt
            sched = pd.read_csv("data/schedule.csv", parse_dates=["date"])
            sched["date"] = sched["date"].dt.date
            from data.schedule import games_by_team, this_week_monday
            return games_by_team(sched, this_week_monday()), True
        except Exception:
            return {}, False

    if spage == "My team":
        names = [n.strip() for n in st.text_area("My roster (one name per line)", height=200,
                                                 key="t_roster").splitlines() if n.strip()]
        mine = board[board["PLAYER"].isin(names)]
        missing = set(names) - set(mine["PLAYER"])
        if missing:
            st.warning("Not found: " + ", ".join(sorted(missing)))
        if len(mine):
            st.dataframe(pretty(mine[["PLAYER", "TEAM", "POS", "MY_VALUE"] + CATS].round(2)),
                         hide_index=True, width="stretch")
            prof = category_profile(mine).rename(index=C.CAT_LABEL)
            st.bar_chart(prof)
            st.info("Weakest: " + ", ".join(prof.sort_values().head(3).index) +
                    ". Target these on waivers unless you're punting them.")

    elif spage == "This week":
        games, ok = games_this_week()
        if not ok:
            st.warning("No schedule file. Run `python data/schedule.py` for real games-per-week; using 3.5 for now.")
        ca, cb = cols(2)
        a = [n.strip() for n in ca.text_area("My active roster", height=200, key="m_a").splitlines() if n.strip()]
        b = [n.strip() for n in cb.text_area("Opponent's active roster", height=200, key="m_b").splitlines() if n.strip()]
        me, opp = board[board["PLAYER"].isin(a)], board[board["PLAYER"].isin(b)]
        if len(me) and len(opp):
            res = compare(me, opp, games)
            res["CAT"] = res["CAT"].map(C.CAT_LABEL)
            st.subheader(f"Projected result: {res.attrs['score']}")
            st.dataframe(res, hide_index=True, width="stretch")
            close = res[res["MARGIN%"].abs() < 8]
            if len(close):
                st.info("Close categories: " + ", ".join(close["CAT"]) + " — stream for these.")

    elif spage == "Waivers":
        games, ok = games_this_week()
        ca, cb = cols(2)
        mw = [n.strip() for n in ca.text_area("My roster", height=180, key="w_m").splitlines() if n.strip()]
        fw = [n.strip() for n in cb.text_area("Free agents (blank = everyone not on my roster)", height=180,
                                              key="w_f").splitlines() if n.strip()]
        mine_w = board[board["PLAYER"].isin(mw)]
        if not fw:
            fw = list(board[~board["PLAYER"].isin(mw)]["PLAYER"].head(150))
        if len(mine_w):
            res = score_free_agents(board, mine_w, fw, games or None, punts=punts)
            st.subheader("Best pickups")
            st.dataframe(res.head(25), hide_index=True, width="stretch")
            st.subheader("Weakest players on my roster")
            st.dataframe(res.attrs["drop_candidates"].round(2), hide_index=True)
        if games:
            st.subheader("Heavy schedule this week (4+ games)")
            st.dataframe(streaming_targets(board, set(mw), games), hide_index=True, width="stretch")
        st.caption(f"You get {C.ADDS_PER_WEEK} adds per week.")

    elif spage == "Injuries":
        try:
            inj = pd.read_csv("data/injuries.csv")
            st.dataframe(inj, hide_index=True, width="stretch")
        except FileNotFoundError:
            st.info("Run `python data/injuries.py` to pull the current report.")

    elif spage == "Rotations":
        st.caption("Each NBA team splits 240 minutes a game. This is who gets them.")
        team = st.selectbox("Team", sorted(pm["TEAM"].dropna().unique()), key="rot_team")
        dc = depth_chart(pm, team)
        st.dataframe(dc, hide_index=True, width="stretch")
        st.bar_chart(dc.set_index("PLAYER")["MIN_WHEN_PLAYING"])
        movers = pm.sort_values("MIN_CHANGE")
        ca, cb = cols(2)
        ca.write("**Gaining minutes**")
        ca.dataframe(movers.tail(12)[["PLAYER", "TEAM", "MIN_WHEN_PLAYING", "MIN_CHANGE"]].round(1)[::-1],
                     hide_index=True)
        cb.write("**Losing minutes**")
        cb.dataframe(movers.head(12)[["PLAYER", "TEAM", "MIN_WHEN_PLAYING", "MIN_CHANGE"]].round(1), hide_index=True)

    elif spage == "All players":
        sv = st.radio("Stats to show", STAT_VIEWS, index=DEFAULT_VIEW, key="s_view", horizontal=not phone)
        q_s = st.text_input("Search player", key="s_q")
        pos_s = st.multiselect("Position", C.BASE_POS, key="s_pos")
        t = merge_stats(board[["PLAYER", "TEAM", "POS", "MY_VALUE", "ADP", "X_RANK"]].copy(), sv, proj, seasons)
        if q_s:
            t = t[t["PLAYER"].str.contains(q_s, case=False, na=False)]
        if pos_s:
            t = t[t["POS"].apply(lambda p: bool(parse_pos(p) & set(pos_s)))]
        st.dataframe(pretty(t.sort_values("MY_VALUE").round(2)), hide_index=True, width="stretch", height=650)
        st.caption("Blank stats mean no 2025-26 numbers exist. DATA = INJ for players who missed last season; "
                   "blank for players with no NBA record yet. Nothing is estimated for them — judge those on "
                   "ADP, XRANK and your own view.")

# ================================================================= SETTINGS
else:
    st.title("League settings")
    st.caption("Add one entry per league. Everything in the tools follows whichever league is selected "
               "in the sidebar.")
    lg = st.session_state.leagues[idx]
    c1, c2, c3 = cols(3)
    lg["name"] = c1.text_input("League name", lg["name"])
    lg["teams"] = c2.number_input("Teams", 4, 30, int(lg["teams"]))
    lg["draft_slot"] = c3.number_input("My draft pick", 1, int(lg["teams"]), int(lg.get("draft_slot", 1)))

    st.subheader("Starting positions")
    st.caption("How many of each slot your league starts. Set a slot to 0 if your league doesn't use it.")
    slot_cols = st.columns(5 if not phone else 2)
    new_slots = {}
    for i, s in enumerate(["PG", "SG", "SF", "PF", "C", "G", "F", "G/F", "F/C", "UTIL"]):
        col = slot_cols[i % len(slot_cols)]
        new_slots[s] = col.number_input(s, 0, 6, int(lg["slots"].get(s, 0)), key=f"slot_{s}")
    lg["slots"] = {k: v for k, v in new_slots.items() if v > 0}

    b1, b2, b3 = cols(3)
    lg["bench"] = b1.number_input("Bench spots", 0, 10, int(lg["bench"]))
    lg["il"] = b2.number_input("IL spots", 0, 6, int(lg["il"]))
    lg["adds"] = b3.number_input("Adds per week", 0, 20, int(lg["adds"]))

    st.info(L.describe(lg))
    a1, a2, a3 = cols(3)
    if a1.button("Save settings", type="primary"):
        L.save(st.session_state.leagues); L.activate(lg); st.cache_data.clear()
        st.success("Saved.")
    if a2.button("Add another league"):
        st.session_state.leagues.append(L.blank(f"League {len(st.session_state.leagues) + 1}"))
        L.save(st.session_state.leagues); st.rerun()
    if a3.button("Delete this league", disabled=len(st.session_state.leagues) == 1):
        st.session_state.leagues.pop(idx); L.save(st.session_state.leagues); st.rerun()
