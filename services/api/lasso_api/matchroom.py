"""A live match: state, stats, the Gaffer's Gauge, moments and Call It markets."""

from __future__ import annotations

import itertools
import math
import time
from dataclasses import dataclass, field

from lasso_engine.explain import shapley
from lasso_engine.inplay import Gaffer, LiveMatch, MatchState
from lasso_engine.markets import generate_markets

from .data import DemoData
from .narrative import driver_rows, template_package

SWING_THRESHOLD = 0.08  # 8 points on either side's win chance triggers a moment
PULSE_EVERY = 15  # match minutes between "pulse" moments
MARKET_EVERY = 4  # match minutes between new Call It challenges
MARKET_OPEN_FOR = 3.0  # match minutes a challenge accepts calls
PITCH_X, PITCH_Y = 105.0, 68.0  # meters; event coordinates are in each team's attacking frame
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
    copy: str | None = None
    status: str = "open"  # open -> closed -> settled
    result: str | None = None
    goals_at_open: tuple[int, int] = (0, 0)

    def public(self) -> dict:
        return {"market_id": self.market_id, "match_id": self.match_id, "question": self.question,
                "options": self.options, "closes": {"period": self.closes[0], "clock": self.closes[1]},
                "status": self.status, "result": self.result, "kind": self.kind, "copy": self.copy}


class MatchRoom:
    def __init__(self, match_id: str, data: DemoData):
        self.match_id = match_id
        self.data = data
        self.meta = data.matches[match_id]
        self.home_id, self.away_id = self.meta["home_id"], self.meta["away_id"]
        self.names = (data.club_name(self.home_id), data.club_name(self.away_id))
        self.reset()

    # ----------------------------------------------------------------- setup
    def reset(self) -> None:
        pre = self.data.prematch[self.match_id]
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
        self.last_market_min = -99.0
        self.last_meter_push = 0.0
        self.started_at: float | None = None
        self.touches: list[dict] = []  # Touchline: recent ball actions, in absolute pitch coordinates
        self.shot_map: list[dict] = []  # every shot of the match, for the Touchline shot map
        self.pending_touches: list[dict] = []
        self.possession: int | None = None
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
            "match_id": self.match_id, "status": self.status,
            "home": {"club_id": self.home_id, "name": self.names[0], **self._club(self.home_id)},
            "away": {"club_id": self.away_id, "name": self.names[1], **self._club(self.away_id)},
            "score": list(s.goals), "reds": list(s.reds), "period": s.period, "clock": round(s.clock, 2),
            "minute": self.minute(), "probs": self.probs(),
            "prematch": {"home": self.pre["p_home"], "draw": self.pre["p_draw"], "away": self.pre["p_away"]},
        }

    def _club(self, cid: str) -> dict:
        c = self.data.clubs[cid]
        return {"short": c["short"], "monogram": c["monogram"], "primary": c["primary"],
                "secondary": c["secondary"]}

    def snapshot(self) -> dict:
        return {**self.summary(), "history": self.history[-400:], "feed": self.feed[-60:],
                "touches": self.touches[-40:], "shots": self.shot_map, "possession": self.possession,
                "moments": self.moments[-12:], "stats": self.stats_public(),
                "markets": [m.public() for m in self.markets.values() if m.status != "settled"][-4:]}

    # ---------------------------------------------------------------- ingest
    def ingest(self, ev: dict) -> list[dict]:
        """Apply one event; return realtime messages to publish."""
        out: list[dict] = []
        if self.status == "scheduled":
            self.status = "live"
            self.started_at = time.time()
            out.append({"type": "status", "match": self.summary()})
            out.extend(self._moment("kickoff", force=True))
            out.extend(self._maybe_open_market(kickoff=True))
        etype = ev["type"]
        t = self.team_index(ev.get("team_id"))
        before_period = self.state.period
        moved = self.live.apply(ev)
        if etype not in ("half_time", "full_time"):
            self.live.advance(int(ev["period"]), float(ev["clock"]))
        if before_period == 1 and self.state.period == 2 and self.status == "half_time":
            self.status = "live"
            out.append({"type": "status", "match": self.summary()})
        self._update_stats(ev, t)
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
            out.extend(self._moment("goal", scorer=self.data.player_label(ev.get("player_id")), focus=t))
        elif etype == "red_card" and t is not None:
            self.window["reds"].append({"team": t, "minute": self.minute()})
            out.extend(self._moment("red_card", red_team=t, focus=1 - t))
        elif etype == "half_time":
            self.status = "half_time"
            out.append({"type": "status", "match": self.summary()})
            out.extend(self._moment("half_time", force=True))
        elif etype == "full_time":
            self.status = "finished"
            out.extend(self._resolve_markets(full_time=True))
            out.append({"type": "status", "match": self.summary()})
            out.extend(self._moment("full_time", force=True))
        else:
            if etype == "shot" and t is not None:
                self.window["xg"][t] += float(ev.get("xg") or 0)
            out.extend(self._resolve_markets())
            out.extend(self._maybe_swing_or_pulse())
            out.extend(self._maybe_open_market())
            out.extend(self._close_markets())

        now = time.time()
        if moved or etype in PUSH_NOW or now - self.last_meter_push > 1.0:
            self.last_meter_push = now
            pt = self._record_point()
            # Touchline rides along with the Gauge update: no extra realtime messages.
            out.append({"type": "meter", "match_id": self.match_id, "point": pt,
                        "score": list(self.state.goals), "minute": self.minute(), "period": self.state.period,
                        "clock": round(self.state.clock, 2), "status": self.status,
                        "touches": self.pending_touches, "possession": self.possession})
            self.pending_touches = []
        return out

    # ------------------------------------------------------------- touchline
    def _abs(self, x, y, t: int) -> tuple[float, float] | None:
        """Home attacks left to right; flip the away team's attacking frame onto the same pitch."""
        if x is None or y is None or (isinstance(x, float) and math.isnan(x)) or (isinstance(y, float) and math.isnan(y)):
            return None
        x, y = float(x), float(y)
        return (round(x, 1), round(y, 1)) if t == 0 else (round(PITCH_X - x, 1), round(PITCH_Y - y, 1))

    def _touch(self, ev: dict, t: int | None) -> dict | None:
        """A compact ball action for the Touchline view."""
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
        # Possession: passes, shots, corners and won tackles/interceptions belong to the acting team.
        if et in ("kickoff", "pass", "shot", "corner", "tackle", "interception", "save"):
            self.possession = t
        if et == "pass" and not tc.get("o"):
            self.possession = 1 - t
        if et == "shot" and (tc.get("g") or not tc.get("on")):
            self.possession = 1 - t  # restart goes to the other side
        tc["pos"] = self.possession
        return tc

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
            if ev.get("outcome"):
                return {**base, "type": "goal", "xg": round(xg, 2), "speed": ev.get("ball_speed_kmh"),
                        "text": f"GOAL! {player} ({team}), {xg:.2f} xG, {ev.get('ball_speed_kmh') or 0:.0f} km/h"}
            if xg >= 0.15 or ev.get("on_target"):
                what = "saved" if ev.get("on_target") else "off target"
                return {**base, "xg": round(xg, 2), "speed": ev.get("ball_speed_kmh"),
                        "text": f"Chance for {player} ({team}), {xg:.2f} xG, {what}"}
            return None
        if et == "red_card":
            return {**base, "text": f"Red card: {player} ({team})"}
        if et == "yellow_card":
            return {**base, "text": f"Yellow card: {player} ({team})"}
        if et == "substitution":
            off = self.data.player_label((ev.get("detail") or "").replace("off:", ""))
            return {**base, "text": f"Sub ({team}): {player} on for {off}"}
        if et == "half_time":
            return {**base, "text": f"Halftime {self.state.goals[0]}-{self.state.goals[1]}"}
        if et == "full_time":
            return {**base, "text": f"Full time {self.state.goals[0]}-{self.state.goals[1]}"}
        return None

    # --------------------------------------------------------------- moments
    def _maybe_swing_or_pulse(self) -> list[dict]:
        p = self.probs()
        lp = self.last_moment_probs
        deltas = {k: p[k] - lp[k] for k in ("home", "draw", "away")}
        if max(abs(v) for v in deltas.values()) >= SWING_THRESHOLD:
            gainer = max(deltas, key=deltas.get)
            if gainer == "draw":  # nobody is surging; the side losing most is the story
                return self._moment("swing_draw", focus=0 if deltas["home"] < deltas["away"] else 1)
            return self._moment("swing", focus=0 if gainer == "home" else 1)
        if self.minute() - self.last_pulse_min >= PULSE_EVERY:
            return self._moment("pulse")
        return []

    def _moment(self, trigger: str, *, force: bool = False, scorer: str | None = None,
                red_team: int | None = None, focus: int | None = None) -> list[dict]:
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
                               red_team=red_team, stats=stats)
        moment = {
            "moment_id": f"{self.match_id}-m{next(_moment_ids)}", "match_id": self.match_id,
            "trigger": trigger, "minute": self.minute(), "period": b.period, "focus": focus,
            "since_minute": int(a.clock), "before": before, "after": after, "drivers": drivers,
            "score": list(b.goals), "window": {k: v for k, v in self.window.items()}, **pkg,
        }
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

    def open_market(self, c, copy: str | None = None) -> list[dict]:
        if c.market_id in self.markets:
            return []
        p, clock = self.state.period, self.state.clock
        closes_clock = min(clock + MARKET_OPEN_FOR, 45 + 1 if p == 1 else 90 + 3)
        if c.market_id.startswith("result") and self.status == "live" and self.minute() < 2:
            closes_clock = 10.0
        m = Market(market_id=f"{self.match_id}:{c.market_id}", match_id=self.match_id, question=c.question,
                   options=c.options, period=p, opened_clock=clock, closes=(p, closes_clock), settles=c.settles,
                   kind=c.market_id.split("-")[0], copy=copy, goals_at_open=tuple(self.state.goals))
        self.markets[m.market_id] = m
        self.last_market_min = self.minute()
        return [{"type": "market_open", "market": m.public()}]

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
