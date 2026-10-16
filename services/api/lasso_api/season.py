"""Season outlook for a live match: the table as it stands and what the result means for the season.

The rest of the season is simulated once per match (about a second, in a worker thread) with the Gaffer's
team strengths as of that matchday. After that, every question is a cheap lookup: each club's title, top-four
and relegation chances if this match ends in a home win, a draw or an away win. The phone blends those with
the live Gauge, so season odds move every second without any extra realtime messages.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import zlib
from collections import defaultdict

from lasso_engine.season import ZONES, SeasonOutlook, apply_result, rank, simulate, stake_zone

from .data import DemoData

log = logging.getLogger("lasso.season")

SIMS = 10_000
_cache: dict[str, SeasonOutlook] = {}
_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)


def get(match_id: str) -> SeasonOutlook | None:
    return _cache.get(match_id)


def compute(data: DemoData, match_id: str) -> SeasonOutlook:
    """Simulate the rest of the season for this match (once; later calls return the cached result)."""
    with _locks[match_id]:
        if match_id in _cache:
            return _cache[match_id]
        m = data.matches[match_id]
        o = simulate(data.matches_df, data.club_ids, int(m["season"]), int(m["matchday"]), m["home_id"],
                     m["away_id"], match_id, data.strength_hyper, sims=SIMS, seed=zlib.crc32(match_id.encode()))
        _cache[match_id] = o
        log.info("season outlook ready for %s: matchday %d, %d fixtures left, %d simulations",
                 match_id, o.matchday, o.remaining, o.sims)
        return o


async def warm(data: DemoData, match_ids: list[str]) -> None:
    for mid in match_ids:
        try:
            await asyncio.to_thread(compute, data, mid)
        except Exception:  # noqa: BLE001 - the app works without it
            log.exception("season outlook failed for %s", mid)


def _r(x: float) -> float:
    return round(float(x), 3)


def _odds(d: dict) -> dict:
    return {**{z: _r(d[z]) for z in ZONES}, "avg_pos": round(float(d["avg_pos"]), 1)}


def public(o: SeasonOutlook, data: DemoData, score: tuple[int, int], prematch: dict[str, float]) -> dict:
    """Everything the phone needs: the table before this match, every club's odds for each result from the
    current score, the two clubs' odds before kickoff, and the race that matters most to each of them."""
    names = {c: data.clubs[c]["name"] for c in o.club_ids}
    t = o.before
    table = [{"club_id": c, "name": names[c], "short": data.clubs[c]["short"], "primary": data.clubs[c]["primary"],
              **{k: int(t.loc[c, k]) for k in ("played", "won", "drawn", "lost", "gf", "ga", "gd", "pts")}}
             for c in rank(t, names)]
    cond = o.conditional(*score)
    at_kickoff = o.conditional(0, 0)
    kick = o.blended(0, 0, prematch)
    stakes = {}
    for side, club in (("home", o.home_id), ("away", o.away_id)):
        zone, spread = stake_zone(at_kickoff, club, side)
        stakes[side] = {"zone": zone, "spread": _r(spread)}
    return {
        "season": o.season, "matchday": o.matchday, "sims": o.sims, "remaining": o.remaining,
        "score": list(score), "table": table,
        "odds": {res: {c: _odds(v) for c, v in by.items()} for res, by in cond.items()},
        "kickoff": {c: _odds(kick[c]) for c in (o.home_id, o.away_id)},
        "stakes": stakes,
    }


def race(o: SeasonOutlook) -> str:
    """The race this match is part of, for the match list: the biggest stake of either club."""
    at_kickoff = o.conditional(0, 0)
    best = max((stake_zone(at_kickoff, c, s) for s, c in (("home", o.home_id), ("away", o.away_id))),
               key=lambda zs: zs[1])
    return best[0]


ZONE_WORDS = {"title": "winning the league", "top4": "a top-four finish", "relegation": "relegation"}


def tool_view(o: SeasonOutlook, data: DemoData, score: tuple[int, int], probs: dict[str, float]) -> dict:
    """The Gaffer's season outlook for agents: plain fields, whole percentages."""
    names = {c: data.clubs[c]["name"] for c in o.club_ids}
    now_table = apply_result(o.before, o.home_id, o.away_id, *score)
    order = rank(now_table, names)
    now = o.blended(*score, probs)
    cond = o.conditional(*score)
    at_kickoff = o.conditional(0, 0)
    pct = lambda x: round(100 * x)  # noqa: E731

    def row(c: str) -> dict:
        return {"position": order.index(c) + 1, "club": names[c], "played": int(now_table.loc[c, "played"]),
                "points": int(now_table.loc[c, "pts"]), "goal_difference": int(now_table.loc[c, "gd"])}

    keep = set(order[:4]) | set(order[-3:])
    for c in (o.home_id, o.away_id):
        k = order.index(c)
        keep |= set(order[max(0, k - 1):k + 2])
    clubs = {}
    for side, c in (("home", o.home_id), ("away", o.away_id)):
        zone, _ = stake_zone(at_kickoff, c, side)
        win, lose = ("home", "away") if side == "home" else ("away", "home")
        entry = {"position_as_it_stands": order.index(c) + 1, "title_chance_pct": pct(now[c]["title"]),
                 "top_four_chance_pct": pct(now[c]["top4"]), "relegation_chance_pct": pct(now[c]["relegation"]),
                 "likely_finish": round(now[c]["avg_pos"])}
        if zone != "none":
            entry["most_at_stake"] = ZONE_WORDS[zone]
            entry["chance_if_they_win_pct"] = pct(cond[win][c][zone])
            entry["chance_if_draw_pct"] = pct(cond["draw"][c][zone])
            entry["chance_if_they_lose_pct"] = pct(cond[lose][c][zone])
        else:
            entry["most_at_stake"] = "little either way: mid-table"
        clubs[names[c]] = entry
    favorites = sorted(o.club_ids, key=lambda c: -now[c]["title"])[:3]
    return {
        "season": o.season, "matchday": o.matchday,
        "table_as_it_stands": [row(c) for c in order if c in keep],
        "this_match": clubs,
        "title_favorites": [{"club": names[c], "title_chance_pct": pct(now[c]["title"])} for c in favorites],
        "how": f"The rest of the season ({o.remaining} matches) simulated {o.sims:,} times with the Gaffer's "
               f"team strengths; top four and the bottom three (relegated) by points, then goal difference.",
    }


def full_time(o: SeasonOutlook, data: DemoData, score: tuple[int, int], prematch: dict[str, float]) -> dict | None:
    """What the final result did to the season of the club with the most at stake: the race, its chance
    before kickoff and now. None when neither club had much riding on it."""
    h, a = score
    at_kickoff = o.conditional(0, 0)
    sides = [("home", o.home_id), ("away", o.away_id)]
    if h != a:
        sides = [sides[0] if h > a else sides[1]] + [sides[1] if h > a else sides[0]]
    else:
        sides.sort(key=lambda sc: -stake_zone(at_kickoff, sc[1], sc[0])[1])
    for side, club in sides:
        zone, _ = stake_zone(at_kickoff, club, side)
        if zone == "none":
            continue
        was = o.blended(0, 0, prematch)[club][zone]
        now = o.odds_given(h, a)[club][zone]
        return {"club": data.clubs[club]["name"], "team": 0 if side == "home" else 1, "zone": zone,
                "was_pct": round(100 * was), "now_pct": round(100 * now)}
    return None
