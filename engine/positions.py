"""Position eligibility, legal roster slotting, and scarcity adjustments."""
import pandas as pd
import config as C


def parse_pos(pos) -> set:
    return {p.strip().upper() for p in str(pos).split(",") if p.strip()}


def _max_match(players, slot_list):
    """Kuhn's maximum bipartite matching: players -> active slots."""
    match_slot = [-1] * len(slot_list)

    def try_player(i, seen):
        for j, s in enumerate(slot_list):
            if j in seen or not (players[i] & C.SLOT_ELIGIBILITY[s]):
                continue
            seen.add(j)
            if match_slot[j] == -1 or try_player(match_slot[j], seen):
                match_slot[j] = i
                return True
        return False

    return sum(try_player(i, set()) for i in range(len(players)))


def can_slot(roster_positions: list, bench: int = C.BENCH) -> bool:
    """True if these players (eligibility sets) can all be rostered legally:
    at most `bench` players unassigned to an active slot."""
    slot_list = [s for s, n in C.ROSTER_SLOTS.items() for _ in range(n)]
    players = list(roster_positions)
    if len(players) > len(slot_list) + bench:
        return False
    need = max(0, len(players) - bench)
    return _max_match(players, slot_list) >= need


def open_slot_needs(roster_positions: list) -> dict:
    """How many more players of each slot type can still be placed in active slots."""
    slot_list = [s for s, n in C.ROSTER_SLOTS.items() for _ in range(n)]
    players = list(roster_positions)
    base = _max_match(players, slot_list)
    remaining = {}
    for s in C.ROSTER_SLOTS:
        probe = list(players)
        k = 0
        while True:
            probe.append(set(C.SLOT_ELIGIBILITY[s]))
            if _max_match(probe, slot_list) > base + k:
                k += 1
            else:
                break
        if k:
            remaining[s] = k
    return remaining


def positional_adjustment(df: pd.DataFrame, value_col: str = "VALUE") -> pd.Series:
    """Value over replacement at the player's best eligible position.

    Replacement = value of the Nth best eligible player, N = POSITION_SLOTS[pos].
    Players eligible at a scarce position (C here: 32 starting slots) get a boost.
    """
    pos_sets = df["POS"].apply(parse_pos)
    repl = {}
    for pos, n in C.POSITION_SLOTS.items():
        mask = pos_sets.apply(lambda s: pos in s)
        elig = df.loc[mask, value_col].sort_values(ascending=False)
        if len(elig) == 0:
            repl[pos] = 0.0
            continue
        idx = min(int(round(n)) - 1, len(elig) - 1)
        repl[pos] = float(elig.iloc[idx])

    def vorp(row, s):
        r = [repl[p] for p in s if p in repl]
        return row - min(r) if r else 0.0

    return pd.Series([vorp(v, s) for v, s in zip(df[value_col], pos_sets)], index=df.index)


def fill_slots(roster_positions: list, names: list) -> list:
    """Assign drafted players to active slots the way a fantasy site does.

    Returns [(slot, player_or_None), ...] in roster order, bench last. Uses maximum matching so a
    multi-position player lands wherever he's most useful rather than first-come-first-served.
    """
    slot_list = [s for s, n in C.ROSTER_SLOTS.items() for _ in range(n)]
    players = list(roster_positions)
    match_slot = [-1] * len(slot_list)

    def try_player(i, seen):
        for j, sl in enumerate(slot_list):
            if j in seen or not (players[i] & C.SLOT_ELIGIBILITY[sl]):
                continue
            seen.add(j)
            if match_slot[j] == -1 or try_player(match_slot[j], seen):
                match_slot[j] = i
                return True
        return False

    for i in range(len(players)):
        try_player(i, set())

    out = [(sl, names[match_slot[j]] if match_slot[j] != -1 else None) for j, sl in enumerate(slot_list)]
    placed = {i for i in match_slot if i != -1}
    bench = [names[i] for i in range(len(players)) if i not in placed]
    for k in range(C.BENCH):
        out.append(("BN", bench[k] if k < len(bench) else None))
    for extra in bench[C.BENCH:]:
        out.append(("—", extra))
    return out
