"""A live match: state, stats, the Gaffer's Gauge, moments and Call It markets."""

from __future__ import annotations

import itertools
import math
import time
import zlib
from dataclasses import dataclass, field

from lasso_engine.explain import shapley
from lasso_engine.impact import ASSIST_SHARE, goal_prevented, swing
from lasso_engine.inplay import Gaffer, LiveMatch, MatchState, odds_multiplier
from lasso_engine.markets import generate_markets

from .data import DemoData
from . import season as season_mod
from .narrative import driver_rows, template_package

SWING_THRESHOLD = 0.08  # 8 points on either side's win chance triggers a moment
PULSE_EVERY = 15  # match minutes between "pulse" moments
CLOCK_SWING_GAP = 15  # match minutes between swings caused mostly by the clock (so "time is running out" isn't
#                       told every six minutes late in a level game; the next one covers the whole drift)
CLOCK_SHARE = 0.7  # a swing is "mostly the clock" when the clock is at least this share of the change
MARKET_EVERY = 4  # match minutes between new Call It challenges
MARKET_OPEN_FOR = 3.0  # match minutes a challenge accepts calls
IMPACT_SHOWN = 5  # players on the Player of the Match leaderboard (and the vote)
VAR_STANDS_RATE = 0.7  # the base rate a checked goal stands, used to price "Will the goal stand?"
PITCH_X, PITCH_Y = 105.0, 68.0  # meters; event coordinates are in each team's attacking frame
BIG_CHANCE_XG = 0.2  # shots this good (and every goal) carry their build-up for the Pitch
MAX_CHAIN = 10
TOUCH_TYPES = {"kickoff", "pass", "shot", "tackle", "interception", "save", "corner", "foul",
               "yellow_card", "red_card", "substitution"}
PUSH_NOW = {"kickoff", "shot", "corner", "red_card", "half_time", "full_time"}
_moment_ids = itertools.count(1)


def _key(period: int, clock: float) -> tuple[int, float]:
    return (period, clock)


@dataclass
class TeamStats:
    passes: int = 0
    passes_completed: int = 0
    difficulty_sum: float = 0.0
    final_third: int = 0
    shots: int = 0
    on_target: int = 0
    xg: float = 0.0
    goals: int = 0
    corners: int = 0
    fouls: int = 0
    yellows: int = 0
    reds: int = 0
    fastest_shot: float = 0.0
    longest_pass: float = 0.0
    shot_log: list[tuple[float, float]] = field(default_factory=list)  # (elapsed, xg)


@dataclass
class Market:
    market_id: str
    match_id: str
    question: str
    options: list[dict]
    period: int
    opened_clock: float
    closes: tuple[int, float]
    settles: str
    kind: str
    copy: dict | str | None = None  # the Game Master's invitation, by language
    status: str = "open"  # open -> closed -> settled
    result: str | None = None
    goals_at_open: tuple[int, int] = (0, 0)
    params: dict = field(default_factory=dict)  # what the app needs to phrase the question in any language

    def public(self) -> dict:
        return {"market_id": self.market_id, "match_id": self.match_id, "question": self.question,
                "options": self.options, "closes": {"period": self.closes[0], "clock": self.closes[1]},
                "status": self.status, "result": self.result, "kind": self.kind, "copy": self.copy,
                "params": self.params}


class MatchRoom:
    def __init__(self, match_id: str, data: DemoData, source: str | None = None):
        self.match_id = match_id  # the room's id (a private replay has its own, like "S5-MD07-03~a1b2c3")
        self.source_id = source or match_id  # the match whose data it plays
        self.private = source is not None and source != match_id
        self.data = data
        self.meta = data.matches[self.source_id]
        self.home_id, self.away_id = self.meta["home_id"], self.meta["away_id"]
        self.names = (data.club_name(self.home_id), data.club_name(self.away_id))
        self.reset()

    # ----------------------------------------------------------------- setup
    def reset(self) -> None:
        pre = self.data.prematch[self.source_id]
        self.pre = pre
        self.gaffer = Gaffer(pre["home_rate"], pre["away_rate"], self.data.params)
        self.live = LiveMatch(self.gaffer, self.home_id, self.away_id)
        self.status = "scheduled"
        self.stats = (TeamStats(), TeamStats())
        self.history: list[dict] = []
        self.feed: list[dict] = []
        self.moments: list[dict] = []
        self.markets: dict[str, Market] = {}
        self.last_moment_state: MatchState = self.live.state.copy()
        self.last_moment_probs = self.gaffer.probabilities(self.live.state)
        self.window = self._empty_window()
        self.last_pulse_min = 0
        self.last_clock_swing = -99
        self.last_market_min = -99.0
        self.last_meter_push = 0.0
        self.started_at: float | None = None
        self.touches: list[dict] = []  # the Pitch: recent ball actions, in absolute pitch coordinates
        self.shot_map: list[dict] = []  # every shot of the match, for the Pitch shot map
        self.pending_touches: list[dict] = []
        self.possession: int | None = None
        self.cards: list[dict] = []  # bookings for the scoreboard: team, yellow/red, surname, minute
        # Touch the sign: per side, the open "behind" spell and the fans who believe in a comeback.
        self.believe: list[dict | None] = [None, None]
        # VAR: the check in progress (None otherwise), and a goal that just survived one (for its headline).
        self.var: dict | None = None
        self.var_stood: int | None = None
        self.var_story: dict | None = None
        self.var_items = 0
        # Player of the Match: each player's impact, the last pass and shot (for assists and saves), the votes.
        self.players: dict[str, dict] = {}
        self.last_pass: dict | None = None
        self.last_shot: dict | None = None
        self.motm_votes: dict[str, str] = {}
        self.motm_winner: str | None = None
        self.crowd: dict[str, int] = {}
        self.motm_since: dict[str, int] = {}  # the minute each fan made their current pick
        self.fans: set[str] = set()  # fans who took part in this match (a call, a question, a vote, the sign)
        self.crowd_at: int | None = None
        self.last_seq = 0
        self._record_point()

    @staticmethod
    def _empty_window() -> dict:
        return {"goals": [], "reds": [], "xg": [0.0, 0.0]}

    def team_index(self, team_id: str | None) -> int | None:
        return 0 if team_id == self.home_id else 1 if team_id == self.away_id else None

    @property
    def state(self) -> MatchState:
        return self.live.state

    def minute(self) -> int:
        s = self.state
        return int(s.clock) if s.period == 1 else int(max(s.clock, 45))

    def probs(self) -> dict:
        p = self.gaffer.probabilities(self.state)
        return {"home": p["home"], "draw": p["draw"], "away": p["away"]}

    def next_goal(self) -> dict:
        """Who scores the next goal (or nobody): a different question from who wins."""
        if self.state.finished:
            return {}
        return {k: round(v, 3) for k, v in self.gaffer.p_next_goal(self.state).items()}

    def _record_point(self) -> dict:
        s = self.state
        p = self.probs()
        pt = {"elapsed": round(s.elapsed, 2), "period": s.period, "clock": round(s.clock, 2), **p}
        self.history.append(pt)
        return pt

    # ----------------------------------------------------------------- stats
    def stats_public(self) -> dict:
        teams = []
        total_passes = sum(t.passes for t in self.stats) or 1
        total_ft = sum(t.final_third for t in self.stats) or 1
        for i, t in enumerate(self.stats):
            momentum = sum(x for e, x in t.shot_log if e >= self.state.elapsed - 10)
            teams.append({
                "club_id": self.home_id if i == 0 else self.away_id,
                "possession": round(100 * t.passes / total_passes),
                "field_tilt": round(100 * t.final_third / total_ft),
                "pass_accuracy": round(100 * t.passes_completed / t.passes) if t.passes else 0,
                "avg_pass_difficulty": round(t.difficulty_sum / t.passes, 3) if t.passes else 0,
                "passes": t.passes, "shots": t.shots, "on_target": t.on_target, "xg": round(t.xg, 2),
                "goals": t.goals, "corners": t.corners, "fouls": t.fouls, "yellows": t.yellows,
                "reds": t.reds, "fastest_shot_kmh": round(t.fastest_shot, 1),
                "longest_pass_m": round(t.longest_pass, 1), "xg_last_10": round(momentum, 2),
            })
        return {"match_id": self.match_id, "teams": teams}

    def summary(self) -> dict:
        s = self.state
        return {
            "match_id": self.match_id, "status": self.status, "source_id": self.source_id, "private": self.private,
            "home": {"club_id": self.home_id, "name": self.names[0], **self._club(self.home_id)},
            "away": {"club_id": self.away_id, "name": self.names[1], **self._club(self.away_id)},
            "score": list(s.goals), "reds": list(s.reds), "period": s.period, "clock": round(s.clock, 2),
            "minute": self.minute(), "probs": self.probs(), "next_goal": self.next_goal(), "cards": self.cards, "believe": self.believe_public(),
            "var": self.var, "race": self.race(),
            "prematch": {"home": self.pre["p_home"], "draw": self.pre["p_draw"], "away": self.pre["p_away"]},
        }

    # ------------------------------------------------------ player of the match
    def _player(self, pid: str, team: int) -> dict:
        p = self.players.get(pid)
        if p is None:
            name = self.data.player_label(pid)
            p = self.players[pid] = {"id": pid, "name": name, "short": name.split()[-1] if name else "", "team": team,
                                     "impact": 0.0, "goals": 0, "assists": 0, "shots": 0, "saves": 0, "reds": 0,
                                     "best": None}
        return p

    def _credit(self, p: dict, kind: str, pts: float) -> None:
        p["impact"] += pts
        if p["best"] is None or abs(pts) > abs(p["best"]["pts"]):
            p["best"] = {"kind": kind, "minute": self.minute(), "pts": round(pts, 1)}

    def _impact(self, ev: dict, t: int | None, pre: MatchState | None) -> list[dict]:
        """Credit the player behind this action with how much it moved their team's chances."""
        et = ev["type"]
        pid = ev.get("player_id")
        if et == "pass" and t is not None:
            if ev.get("outcome"):
                self.last_pass = {"team": t, "player": pid, "receiver": ev.get("receiver_id"),
                                  "clock": float(ev["clock"]), "period": int(ev["period"])}
            return []
        if t is None or not pid:
            return []
        if et == "shot" and pre is not None:
            pts = swing(self.gaffer, pre, self.state, t)
            p = self._player(pid, t)
            xg = float(ev.get("xg") or 0)
            if ev.get("outcome"):
                p["goals"] += 1
                self._credit(p, "goal", pts)
                lp = self.last_pass
                if (lp and lp["team"] == t and lp["receiver"] == pid and lp["player"] != pid
                        and lp["period"] == int(ev["period"]) and float(ev["clock"]) - lp["clock"] < 0.5):
                    a = self._player(lp["player"], t)
                    a["assists"] += 1
                    self._credit(a, "assist", ASSIST_SHARE * pts)
            else:
                p["shots"] += 1
                self._credit(p, "chance", pts)
                if ev.get("on_target"):
                    self.last_shot = {"team": t, "xg": xg, "clock": float(ev["clock"])}
            self.last_pass = None
        elif et == "save":
            ls = self.last_shot
            if ls and ls["team"] == 1 - t and abs(float(ev["clock"]) - ls["clock"]) < 0.2:
                pts = goal_prevented(self.gaffer, self.state, t, ls["xg"])
                p = self._player(pid, t)
                p["saves"] += 1
                self._credit(p, "save", pts)
            self.last_shot = None
        elif et == "red_card" and pre is not None:
            p = self._player(pid, t)
            p["reds"] += 1
            self._credit(p, "red", swing(self.gaffer, pre, self.state, t))
        else:
            return []
        return [{"type": "impact", "match_id": self.match_id, "impact": self.impact_public()}]

    def leaders(self, n: int = IMPACT_SHOWN) -> list[dict]:
        return sorted(self.players.values(), key=lambda p: -p["impact"])[:n]

    def vote_open(self) -> bool:
        """Fans vote from halftime to the final whistle."""
        return self.status == "half_time" or (self.status == "live" and self.state.period == 2)

    def _crowd_tick(self) -> None:
        """The simulated crowd's votes (like the bot players in Call It). A first wave votes at halftime and
        more fans join every minute, each picking mostly the biggest impact at that moment (goalscorers get a
        little extra love). Votes, once cast, stay, so an early hero keeps fans after a late winner."""
        if not self.vote_open():
            return
        leaders = self.leaders()
        if not leaders:
            return
        m = self.minute()
        if self.crowd_at is None:
            n = 240 + zlib.crc32(self.match_id.encode()) % 300
        else:
            n = int(9 * (m - self.crowd_at))
        if n <= 0:
            return
        self.crowd_at = m
        w = [math.exp(min(60.0, max(-20.0, p["impact"])) / 9) * (1.3 if p["goals"] else 1.0) for p in leaders]
        total = sum(w)
        for p, x in zip(leaders, w):
            self.crowd[p["id"]] = self.crowd.get(p["id"], 0) + int(n * x / total)

    def impact_public(self, user_id: str | None = None) -> dict:
        self._crowd_tick()
        leaders = self.leaders()
        counts = dict(self.crowd)
        for pid in self.motm_votes.values():
            counts[pid] = counts.get(pid, 0) + 1
        total = sum(counts.values())
        players = [{k: (round(v, 1) if k == "impact" else v) for k, v in p.items()} for p in leaders]
        return {
            "players": players, "open": self.vote_open(), "winner": self.motm_winner,
            "votes": {pid: round(c / total, 3) for pid, c in counts.items()} if total else {},
            "voters": total, "mine": self.motm_votes.get(user_id) if user_id else None,
        }

    def vote(self, user_id: str, player_id: str) -> dict | None:
        if not self.vote_open() or player_id not in self.players:
            return None
        if self.motm_votes.get(user_id) != player_id:
            self.motm_since[user_id] = self.minute()
        self.motm_votes[user_id] = player_id
        self.fans.add(user_id)
        return self.impact_public(user_id)

    def _motm_result(self) -> list[dict]:
        """Full time: the Gaffer's Player of the Match is the biggest impact. Fans who picked them get paid."""
        leaders = self.leaders(1)
        if not leaders:
            return []
        self.motm_winner = leaders[0]["id"]
        winners = sorted(u for u, pid in self.motm_votes.items() if pid == self.motm_winner)
        big = (leaders[0]["best"] or {}).get("minute", 0)
        early = [u for u in winners if self.motm_since.get(u, 999) < big]  # picked before their big moment
        return [{"type": "motm_result", "match_id": self.match_id, "player": leaders[0]["name"],
                 "team": leaders[0]["team"], "users": winners, "early": early, "minute": big}]

    def climbs(self) -> list[dict]:
        """Full time: clubs in this match that climbed three or more places in the table, for On the Up."""
        o = season_mod.get(self.source_id)
        if not o:
            return []
        from lasso_engine.season import apply_result, rank  # local: only needed once per match
        names = {c: self.data.clubs[c]["name"] for c in o.club_ids}
        before = rank(o.before, names)
        after = rank(apply_result(o.before, self.home_id, self.away_id, *self.state.goals), names)
        out = []
        for club in (self.home_id, self.away_id):
            up = before.index(club) - after.index(club)
            if up >= 3:
                out.append({"type": "climb", "match_id": self.match_id, "club_id": club, "club": names[club],
                            "places": up, "position": after.index(club) + 1, "users": sorted(self.fans)})
        return out

    def impact_tool(self) -> dict:
        """Player of the Match for agents: the impact leaderboard with what each player did."""
        side = lambda p: self.names[p["team"]]  # noqa: E731
        return {
            "how": "Impact is how much a player's own actions moved their team's chances (win plus half a draw), "
                   "in percentage points: goals, a quarter of the goal for the assist, chances, saves (the goal "
                   "prevented) and red cards (negative).",
            "leaders": [{"player": p["name"], "club": side(p), "impact_pts": round(p["impact"], 1),
                         "goals": p["goals"], "assists": p["assists"], "shots": p["shots"], "saves": p["saves"],
                         "red_cards": p["reds"],
                         "biggest_moment": p["best"] and f"{p['best']['kind']} at {p['best']['minute']}' "
                                                         f"({p['best']['pts']:+.1f} pts)"}
                        for p in self.leaders(6)],
            "player_of_the_match": self.players[self.motm_winner]["name"] if self.motm_winner else None,
        }

    # ---------------------------------------------------------------- season
    def _prematch_probs(self) -> dict[str, float]:
        return {"home": self.pre["p_home"], "draw": self.pre["p_draw"], "away": self.pre["p_away"]}

    def race(self) -> str | None:
        o = season_mod.get(self.source_id)
        return season_mod.race(o) if o else None

    def season_public(self) -> dict | None:
        """The season outlook from the current score, or None until the simulations are ready."""
        o = season_mod.get(self.source_id)
        return season_mod.public(o, self.data, tuple(self.state.goals), self._prematch_probs()) if o else None

    def season_tool(self) -> dict | None:
        o = season_mod.get(self.source_id)
        if not o:
            return None
        p = self.probs()
        return season_mod.tool_view(o, self.data, tuple(self.state.goals), {k: p[k] for k in ("home", "draw", "away")})

    def _season_msg(self) -> list[dict]:
        pub = self.season_public()
        return [{"type": "season", "match_id": self.match_id, "season": pub}] if pub else []

    def _club(self, cid: str) -> dict:
        c = self.data.clubs[cid]
        return {"short": c["short"], "monogram": c["monogram"], "primary": c["primary"],
                "secondary": c["secondary"]}

    def snapshot(self) -> dict:
        return {**self.summary(), "history": self.history[-400:], "feed": self.feed[-150:],
                "touches": self.touches[-40:], "shots": self.shot_map, "possession": self.possession,
                "moments": self.moments[-12:], "stats": self.stats_public(),
                "markets": [m.public() for m in self.markets.values() if m.status != "settled"][-4:],
                "season": self.season_public(), "impact": self.impact_public()}

    # ---------------------------------------------------------------- ingest
    def catch_up(self, upto_seq: int) -> int:
        """Silently apply any events we missed before `upto_seq` (e.g. the API restarted mid-match).

        The synthetic match is in our own data, so state, score, stats and the Gauge stay correct even
        when the live stream is joined part-way through. Returns how many events were replayed.
        """
        missed = [e for e in self.data.events_for(self.source_id) if self.last_seq < int(e["seq"]) < upto_seq]
        for e in missed:
            self.ingest(e)
        self.pending_touches = []
        return len(missed)

    def ingest(self, ev: dict) -> list[dict]:
        """Apply one event; return realtime messages to publish."""
        out: list[dict] = []
        self.last_seq = max(self.last_seq, int(ev.get("seq") or 0))
        if self.status == "scheduled":
            self.status = "live"
            self.started_at = time.time()
            out.append({"type": "status", "match": self.summary()})
            out.extend(self._moment("kickoff", force=True))
            out.extend(self._season_msg())
            out.extend(self._maybe_open_market(kickoff=True))
        etype = ev["type"]
        t = self.team_index(ev.get("team_id"))
        if etype in ("var_check", "var_decision"):
            return out + (self._var_event(ev, t) if t is not None else [])
        before_period = self.state.period
        scored = etype in ("shot", "red_card") and t is not None and ev.get("player_id")
        if scored:  # move the clock to the moment of the action first, so the clock isn't credited to anyone
            self.live.advance(int(ev["period"]), float(ev["clock"]))
            pre = self.state.copy()
        moved = self.live.apply(ev)
        impact_msgs = self._impact(ev, t, pre if scored else None)
        if etype not in ("half_time", "full_time"):
            self.live.advance(int(ev["period"]), float(ev["clock"]))
        if before_period == 1 and self.state.period == 2 and self.status == "half_time":
            self.status = "live"
            out.append({"type": "status", "match": self.summary()})
        self._update_stats(ev, t)
        if etype in ("yellow_card", "red_card") and t is not None:
            name = self.data.player_label(ev.get("player_id"))
            self.cards.append({"k": t, "c": "r" if etype == "red_card" else "y",
                               "p": name.split()[-1] if name else "", "m": self.minute()})
            out.append({"type": "status", "match": self.summary()})
        touch = self._touch(ev, t)
        if touch:
            self.touches.append(touch)
            del self.touches[:-80]
            if touch["t"] == "shot":
                self.shot_map.append(touch)
            self.pending_touches.append(touch)
        item = self._feed_item(ev, t)
        if item:
            self.feed.append(item)
            out.append({"type": "event", "match_id": self.match_id, "event": item})

        if etype == "shot" and ev.get("outcome") and t is not None:
            self.window["goals"].append({"team": t, "minute": self.minute(),
                                         "player": self.data.player_label(ev.get("player_id"))})
            out.extend(self._resolve_markets(goal_team=t))
            out.extend(self._moment("goal", scorer=self.data.player_label(ev.get("player_id")), focus=t,
                                    var={"stood": True} if self.var_stood == t else None))
            self.var_stood = None
            out.extend(self._season_msg())  # the table and the season odds move with every goal
            out.extend(self._update_believe())
        elif etype == "red_card" and t is not None:
            self.window["reds"].append({"team": t, "minute": self.minute()})
            out.extend(self._moment("red_card", red_team=t, focus=1 - t,
                                    player=self.data.player_label(ev.get("player_id"))))
        elif etype == "half_time":
            self.status = "half_time"
            out.append({"type": "status", "match": self.summary()})
            out.extend(self._moment("half_time", force=True))
        elif etype == "full_time":
            self.status = "finished"
            self.believe = [None, None]  # still behind at the final whistle: the sign comes down, no reward
            out.extend(self._resolve_markets(full_time=True))
            out.append({"type": "status", "match": self.summary()})
            o = season_mod.get(self.source_id)
            ft = season_mod.full_time(o, self.data, tuple(self.state.goals), self._prematch_probs()) if o else None
            out.extend(self._moment("full_time", force=True, season=ft))
            out.extend(self._motm_result())
            out.extend(self.climbs())
        else:
            if etype == "shot" and t is not None:
                self.window["xg"][t] += float(ev.get("xg") or 0)
            out.extend(self._resolve_markets())
            out.extend(self._maybe_swing_or_pulse())
            out.extend(self._maybe_open_market())
            out.extend(self._close_markets())

        if ev.get("var_disallowed") and self.var_story and t is not None:
            story, self.var_story = self.var_story, None
            out.extend(self._moment("var_overturned", force=True, focus=story["team"],
                                    var={k: story[k] for k in ("reason", "player", "stands_pct")}))
        out.extend(impact_msgs)
        now = time.time()
        if moved or etype in PUSH_NOW or now - self.last_meter_push > 1.0:
            self.last_meter_push = now
            pt = self._record_point()
            # The Pitch rides along with the Gauge update: no extra realtime messages.
            out.append({"type": "meter", "match_id": self.match_id, "point": pt,
                        "score": list(self.state.goals), "minute": self.minute(), "period": self.state.period,
                        "clock": round(self.state.clock, 2), "status": self.status,
                        "touches": self.pending_touches, "possession": self.possession,
                        "believe": self.believe_public()})
            self.pending_touches = []
        return out

    # ---------------------------------------------------------------- pitch
    def _abs(self, x, y, t: int) -> tuple[float, float] | None:
        """Home attacks left to right; flip the away team's attacking frame onto the same pitch."""
        if x is None or y is None or (isinstance(x, float) and math.isnan(x)) or (isinstance(y, float) and math.isnan(y)):
            return None
        x, y = float(x), float(y)
        return (round(x, 1), round(y, 1)) if t == 0 else (round(PITCH_X - x, 1), round(PITCH_Y - y, 1))

    def _touch(self, ev: dict, t: int | None) -> dict | None:
        """A compact ball action for the Pitch view."""
        et = ev["type"]
        if et not in TOUCH_TYPES or t is None:
            return None
        tc: dict = {"s": int(ev["seq"]), "t": et, "k": t, "m": self.minute(),
                    "p": self.data.player_label(ev.get("player_id"))}
        start = self._abs(ev.get("x"), ev.get("y"), t)
        if et == "save" and start is None:
            start = (2.0, 34.0) if t == 0 else (PITCH_X - 2.0, 34.0)  # the keeper at their own goal
        if start:
            tc["x"], tc["y"] = start
        end = self._abs(ev.get("end_x"), ev.get("end_y"), t)
        if et == "pass":
            if end:
                tc["ex"], tc["ey"] = end
            tc["o"] = bool(ev.get("outcome"))
            if ev.get("receiver_id") and tc["o"]:
                tc["r"] = self.data.player_label(ev.get("receiver_id"))
        elif et == "shot":
            tc["xg"] = round(float(ev.get("xg") or 0), 2)
            tc["g"] = bool(ev.get("outcome"))
            tc["on"] = bool(ev.get("on_target"))
            if tc["g"] or tc["xg"] >= BIG_CHANCE_XG:
                tc["chain"] = self._build_up(t)
        # Possession: passes, shots, corners and won tackles/interceptions belong to the acting team.
        if et in ("kickoff", "pass", "shot", "corner", "tackle", "interception", "save"):
            self.possession = t
        if et == "pass" and not tc.get("o"):
            self.possession = 1 - t
        if et == "shot" and (tc.get("g") or not tc.get("on")):
            self.possession = 1 - t  # restart goes to the other side
        tc["pos"] = self.possession
        return tc

    def _build_up(self, t: int) -> dict:
        """How a goal or big chance was built: the run of completed passes by the shooting side just before it,
        and how that spell on the ball began (a won tackle or interception, a corner, the kickoff)."""
        passes: list[list] = []
        start = None
        for x in reversed(self.touches):
            if x["t"] == "pass" and x["k"] == t and x.get("o") and "ex" in x and len(passes) < MAX_CHAIN:
                passes.append([round(x["x"], 1), round(x["y"], 1), round(x["ex"], 1), round(x["ey"], 1), x["p"]])
                continue
            if x["k"] == t and x["t"] in ("tackle", "interception", "corner", "kickoff", "save") and "x" in x:
                start = {"t": x["t"], "p": x["p"], "x": round(x["x"], 1), "y": round(x["y"], 1)}
            break
        passes.reverse()
        return {"passes": passes, "start": start}

    def _update_stats(self, ev: dict, t: int | None) -> None:
        if t is None:
            return
        st = self.stats[t]
        et = ev["type"]
        if et == "pass":
            st.passes += 1
            st.passes_completed += 1 if ev.get("outcome") else 0
            st.difficulty_sum += float(ev.get("pass_difficulty") or 0)
            if (ev.get("end_x") or 0) > 70:
                st.final_third += 1
            st.longest_pass = max(st.longest_pass, float(ev.get("pass_length") or 0))
        elif et == "shot":
            st.shots += 1
            st.xg += float(ev.get("xg") or 0)
            st.on_target += 1 if ev.get("on_target") else 0
            st.fastest_shot = max(st.fastest_shot, float(ev.get("ball_speed_kmh") or 0))
            st.shot_log.append((self.state.elapsed, float(ev.get("xg") or 0)))
            if ev.get("outcome"):
                st.goals += 1
        elif et == "corner":
            st.corners += 1
        elif et == "foul":
            st.fouls += 1
        elif et == "yellow_card":
            st.yellows += 1
        elif et == "red_card":
            st.reds += 1

    def _feed_item(self, ev: dict, t: int | None) -> dict | None:
        et = ev["type"]
        player = self.data.player_label(ev.get("player_id"))
        team = self.names[t] if t is not None else ""
        base = {"seq": ev["seq"], "type": et, "minute": self.minute(), "period": ev["period"],
                "team": t, "player": player, "score": list(self.state.goals)}
        if et == "shot":
            xg = float(ev.get("xg") or 0)
            if ev.get("var_disallowed"):
                return None
            if ev.get("outcome"):
                pen = " (penalty)" if ev.get("is_penalty") else ""
                return {**base, "type": "goal", "xg": round(xg, 2), "speed": ev.get("ball_speed_kmh"), "penalty": bool(pen),
                        "text": f"GOAL! {player} ({team}){pen}, {xg:.2f} xG, {ev.get('ball_speed_kmh') or 0:.0f} km/h"}
            if xg >= 0.15 or ev.get("on_target"):
                what = "saved" if ev.get("on_target") else "off target"
                return {**base, "xg": round(xg, 2), "speed": ev.get("ball_speed_kmh"), "on": bool(ev.get("on_target")),
                        "text": f"Chance for {player} ({team}), {xg:.2f} xG, {what}"}
            return None
        if et == "red_card":
            return {**base, "text": f"Red card: {player} ({team})"}
        if et == "yellow_card":
            return {**base, "text": f"Yellow card: {player} ({team})"}
        if et == "substitution":
            off = self.data.player_label((ev.get("detail") or "").replace("off:", ""))
            return {**base, "off": off, "text": f"Sub ({team}): {player} on for {off}"}
        if et == "half_time":
            return {**base, "text": f"Halftime {self.state.goals[0]}-{self.state.goals[1]}"}
        if et == "full_time":
            return {**base, "text": f"Full time {self.state.goals[0]}-{self.state.goals[1]}"}
        return None

    # -------------------------------------------------------------------- VAR
    def _probs_with(self, team: int, xg: float, goal: bool) -> dict:
        s = self.state.copy()
        s.xg[team] += xg
        if goal:
            s.goals[team] += 1
        p = self.gaffer.probabilities(s)
        return {"home": p["home"], "draw": p["draw"], "away": p["away"]}

    def _var_feed(self, t: int, player: str, kind: str, reason: str, decision: str | None = None) -> dict:
        self.var_items += 1
        item = {"seq": 10_000_000 + self.var_items, "type": kind, "minute": self.minute(), "period": self.state.period,
                "team": t, "player": player, "score": list(self.state.goals), "reason": reason,
                "text": f"VAR check: possible {reason} ({player}, {self.names[t]})" if decision is None else
                        f"VAR: goal stands ({player}, {self.names[t]})" if decision == "stands" else
                        f"VAR: no goal, {reason} ({player}, {self.names[t]})"}
        if decision:
            item["decision"] = decision
        self.feed.append(item)
        return {"type": "event", "match_id": self.match_id, "event": item}

    def _var_event(self, ev: dict, t: int) -> list[dict]:
        """The ball's in the net and VAR is checking: the Gauge shows both outcomes and a quick call opens.
        Then the decision: the goal stands (its own event follows) or it's ruled out (a story says so)."""
        player = self.data.player_label(ev.get("player_id"))
        reason = ev.get("reason") or "offside"
        xg = float(ev.get("xg") or 0)
        mid = f"{self.match_id}:var-{self.state.period}-{int(float(ev['clock']) * 10)}"
        out: list[dict] = []
        if ev["type"] == "var_check":
            self.var = {"status": "checking", "team": t, "player": player, "reason": reason, "minute": self.minute(),
                        "stands": self._probs_with(t, xg, True), "ruled_out": self._probs_with(t, xg, False)}
            out.append({"type": "var", "match_id": self.match_id, "var": self.var})
            out.append(self._var_feed(t, player, "var_check", reason))
            if self.status == "live" and mid not in self.markets:
                p = VAR_STANDS_RATE
                m = Market(market_id=mid, match_id=self.match_id, question="Will the goal stand?",
                           options=[{"id": "yes", "label": "It stands", "p": p, "multiplier": odds_multiplier(p)},
                                    {"id": "no", "label": "Ruled out", "p": 1 - p,
                                     "multiplier": odds_multiplier(1 - p)}],
                           period=self.state.period, opened_clock=self.state.clock,
                           closes=(self.state.period, self.state.clock + 0.5), settles=f"var:{t}", kind="var",
                           goals_at_open=tuple(self.state.goals), params={"team": self.names[t]})
                self.markets[mid] = m
                out.append({"type": "market_open", "market": m.public()})
            return out
        decision = ev.get("decision") or "stands"
        self.var = None
        self.var_stood = t if decision == "stands" else None
        out.append({"type": "var", "match_id": self.match_id, "var": None,
                    "decision": {"status": decision, "team": t, "player": player, "reason": reason,
                                 "minute": self.minute()}})
        out.append(self._var_feed(t, player, "var_decision", reason, decision))
        m = self.markets.get(mid)
        if m and m.status != "settled":
            m.status, m.result = "settled", "yes" if decision == "stands" else "no"
            out.append({"type": "market_settled", "market": m.public()})
        if decision == "ruled_out":
            # The story waits for the disallowed shot itself, so its chance includes that shot's xG and matches
            # the "if it's ruled out" figure fans just saw.
            self.var_story = {"reason": reason, "player": player, "team": t,
                              "stands_pct": round(100 * self._probs_with(t, xg, True)["home" if t == 0 else "away"])}
        return out

    # ---------------------------------------------------------- touch the sign
    def _believers(self, spell: dict) -> int:
        """Real fans who touched the sign, plus the simulated crowd (like the bot players in Call It),
        which grows the longer the side is behind."""
        minutes = max(0.0, self.state.elapsed - spell["since"])
        return len(spell["users"]) + spell["base"] + int(spell["rate"] * minutes)

    def believe_public(self) -> list[dict | None]:
        return [None if b is None else {"spell": b["spell"], "count": self._believers(b)} for b in self.believe]

    def _update_believe(self) -> list[dict]:
        """After a goal: open a spell for a side that just fell behind; close it for a side that drew level
        or went ahead, so its believers can be paid."""
        out: list[dict] = []
        g = self.state.goals
        for side in (0, 1):
            behind = g[side] < g[1 - side]
            spell = self.believe[side]
            if behind and spell is None:
                seed = zlib.crc32(f"{self.match_id}:{side}:{self.last_seq}".encode())
                self.believe[side] = {"spell": self.last_seq, "users": set(), "base": 180 + seed % 520,
                                      "rate": 14 + seed % 19, "since": self.state.elapsed}
            elif not behind and spell is not None:
                self.believe[side] = None
                out.append({"type": "believe_result", "match_id": self.match_id, "side": side,
                            "minute": self.minute(), "count": self._believers(spell),
                            "users": sorted(spell["users"])})
        return out

    def touch_sign(self, user_id: str, side: int) -> dict | None:
        spell = self.believe[side]
        if spell is None or self.status not in ("live", "half_time"):
            return None
        new = user_id not in spell["users"]
        spell["users"].add(user_id)
        self.fans.add(user_id)
        return {"side": side, "spell": spell["spell"], "count": self._believers(spell), "new": new}

    # --------------------------------------------------------------- moments
    def _maybe_swing_or_pulse(self) -> list[dict]:
        p = self.probs()
        lp = self.last_moment_probs
        deltas = {k: p[k] - lp[k] for k in ("home", "draw", "away")}
        if max(abs(v) for v in deltas.values()) >= SWING_THRESHOLD:
            side = "home" if abs(deltas["home"]) >= abs(deltas["away"]) else "away"
            parts = shapley(self.gaffer, self.last_moment_state, self.state, side).contributions
            total = sum(abs(v) for v in parts.values()) or 1.0
            clocky = abs(parts.get("clock", 0.0)) / total >= CLOCK_SHARE
            if clocky and self.minute() - self.last_clock_swing < CLOCK_SWING_GAP:
                return []  # only the clock moved it, and we said so recently: wait, then tell the whole drift
            if clocky:
                self.last_clock_swing = self.minute()
            gainer = max(deltas, key=deltas.get)
            if gainer == "draw":  # nobody is surging; the side losing most is the story
                return self._moment("swing_draw", focus=0 if deltas["home"] < deltas["away"] else 1)
            return self._moment("swing", focus=0 if gainer == "home" else 1)
        if self.minute() - self.last_pulse_min >= PULSE_EVERY:
            return self._moment("pulse")
        return []

    def _moment(self, trigger: str, *, force: bool = False, scorer: str | None = None,
                red_team: int | None = None, focus: int | None = None, var: dict | None = None,
                season: dict | None = None, player: str | None = None) -> list[dict]:
        a, b = self.last_moment_state, self.state.copy()
        before, after = self.last_moment_probs, self.probs()
        if focus is None:
            focus = 0 if (after["home"] - before["home"]) >= (after["away"] - before["away"]) else 1
        side = "home" if focus == 0 else "away"
        att = shapley(self.gaffer, a, b, side)
        drivers = driver_rows(att.contributions, self.window, self.names, focus)
        stats = self.stats_public()
        pkg = template_package(trigger=trigger, names=self.names, score=tuple(b.goals), minute=self.minute(),
                               before=before, after=after, focus=focus, drivers=drivers, scorer=scorer,
                               red_team=red_team, stats=stats, var=var, season=season)
        moment = {
            "moment_id": f"{self.match_id}-m{next(_moment_ids)}", "match_id": self.match_id,
            "trigger": trigger, "minute": self.minute(), "period": b.period, "focus": focus,
            "since_minute": int(a.clock), "before": before, "after": after, "drivers": drivers,
            "score": list(b.goals), "window": {k: v for k, v in self.window.items()}, **pkg,
        }
        if scorer or player:  # the scorer, or the player sent off: the Narrator names them
            moment["player"] = scorer or player
        if var:
            moment["var"] = var
        if season:
            moment["season"] = season
        self.moments.append(moment)
        self.last_moment_state, self.last_moment_probs = b, after
        self.window = self._empty_window()
        self.last_pulse_min = self.minute()
        return [{"type": "moment", "moment": moment}]

    # --------------------------------------------------------------- markets
    def _now(self) -> tuple[int, float]:
        return (self.state.period, self.state.clock)

    def _maybe_open_market(self, kickoff: bool = False) -> list[dict]:
        if self.status not in ("live",) or self.state.finished:
            return []
        if not kickoff and self.minute() - self.last_market_min < MARKET_EVERY:
            return []
        if (self.state.period == 2 and self.state.clock > 86) or (self.state.period == 1 and self.state.clock > 41):
            return []
        if sum(1 for m in self.markets.values() if m.status == "open") >= 2:
            return []
        cands = generate_markets(self.gaffer, self.state, self.names[0], self.names[1])
        pick = self.pick_market(cands, kickoff)
        if pick is None:
            return []
        return self.open_market(pick)

    def pick_market(self, cands, kickoff: bool):
        """Offline Game Master: prefer genuinely uncertain, short-horizon questions."""
        if kickoff:
            return next((c for c in cands if c.market_id.startswith("result")), None)

        def interest(c) -> float:
            ps = [o["p"] for o in c.options]
            ent = -sum(p * math.log(p) for p in ps if p > 0) / math.log(len(ps))
            bonus = {"score": 0.15, "comeback": 0.25, "next": 0.05, "result": 0.0}[c.market_id.split("-")[0]]
            return ent + bonus

        # One live question per settlement rule: no stacking three "who scores next?" calls on one goal.
        pending = {m.settles.split(":until")[0] for m in self.markets.values() if m.status != "settled"}
        cands = [c for c in cands if c.market_id.split("-")[0] != "result"
                 and c.settles.split(":until")[0] not in pending
                 and min(o["p"] for o in c.options) >= (0.06 if len(c.options) == 2 else 0.04)]
        recent = {m.kind for m in list(self.markets.values())[-2:]}
        cands.sort(key=lambda c: interest(c) - (0.3 if c.market_id.split("-")[0] in recent else 0), reverse=True)
        return cands[0] if cands else None

    def open_market(self, c, copy: dict | str | None = None) -> list[dict]:
        if c.market_id in self.markets:
            return []
        p, clock = self.state.period, self.state.clock
        closes_clock = min(clock + MARKET_OPEN_FOR, 45 + 1 if p == 1 else 90 + 3)
        if c.market_id.startswith("result") and self.status == "live" and self.minute() < 2:
            closes_clock = 10.0
        m = Market(market_id=f"{self.match_id}:{c.market_id}", match_id=self.match_id, question=c.question,
                   options=c.options, period=p, opened_clock=clock, closes=(p, closes_clock), settles=c.settles,
                   kind=c.market_id.split("-")[0], copy=copy, goals_at_open=tuple(self.state.goals),
                   params=self._market_params(c.settles))
        self.markets[m.market_id] = m
        self.last_market_min = self.minute()
        return [{"type": "market_open", "market": m.public()}]

    def _market_params(self, settles: str) -> dict:
        rule = settles.split(":")
        if rule[0] == "team_goal":
            return {"team": self.names[int(rule[1])], "until": int(float(rule[3]))}
        if rule[0] in ("not_lose", "var"):
            return {"team": self.names[int(rule[1])]}
        return {}

    def _close_markets(self) -> list[dict]:
        out = []
        for m in self.markets.values():
            if m.status == "open" and self._now() >= m.closes:
                m.status = "closed"
                out.append({"type": "market_closed", "market": m.public()})
        return out

    def _resolve_markets(self, goal_team: int | None = None, full_time: bool = False) -> list[dict]:
        out = []
        now = self._now()
        for m in self.markets.values():
            if m.status == "settled":
                continue
            rule = m.settles.split(":")
            result = None
            if rule[0] == "team_goal":
                team, until = int(rule[1]), float(rule[3])
                if goal_team == team and now <= (m.period, until + 0.5):
                    result = "yes"
                elif full_time or now > (m.period, until) or (m.period == 1 and now[0] == 2):
                    result = "no"
            elif rule[0] == "next_goal":
                if goal_team is not None:
                    result = "home" if goal_team == 0 else "away"
                elif full_time:
                    result = "none"
            elif rule[0] == "not_lose" and full_time:
                team = int(rule[1])
                diff = self.state.goals[team] - self.state.goals[1 - team]
                result = "yes" if diff >= 0 else "no"
            elif rule[0] == "result" and full_time:
                g = self.state.goals
                result = "home" if g[0] > g[1] else "away" if g[1] > g[0] else "draw"
            if result:
                m.status, m.result = "settled", result
                out.append({"type": "market_settled", "market": m.public()})
        return out
