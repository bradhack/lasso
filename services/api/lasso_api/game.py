"""Beat the Gaffer: calls, biscuits, streaks, the Goldfish, stickers, missions and leagues."""

from __future__ import annotations

import datetime as dt
import math
import random
import secrets
import time
import uuid

from lasso_engine.markets import calibration_points

from .matchroom import Market, MatchRoom
from .stickers import award, public_stickers
from .store import Store

START_BISCUITS = 1000
STAKES = (50, 100, 250)
BELIEVE_REWARD = 50  # Touch the sign: paid to believers when their side draws level
MOTM_REWARD = 30  # Player of the Match: paid to fans whose pick matches the Gaffer's (the biggest impact)
MISSIONS = {
    "correct_calls": {"target": 3, "reward": 150, "label": "Win 3 calls"},
    "underdog": {"target": 1, "reward": 200, "label": "Win a call the Gaffer gave under 25%"},
    "stories": {"target": 2, "reward": 50, "label": "Read 2 \"Why it moved\" stories"},
}
BOTS = [("Priya", 0.62), ("Sam", 0.58), ("Marcus", 0.52), ("Jo", 0.55), ("Aisha", 0.6), ("Tom", 0.48)]
DEFAULT_LEAGUE = "DIAMOND"


def _today() -> str:
    return dt.date.today().isoformat()


def _iso_week() -> str:
    y, w, _ = dt.date.today().isocalendar()
    return f"{y}-W{w:02d}"


def level_for(xp: int) -> int:
    return int(math.sqrt(max(xp, 0) / 50)) + 1


def streak_bonus(streak: int) -> float:
    return 1.5 if streak >= 5 else 1.25 if streak >= 3 else 1.0


def new_user(name: str, *, club_id: str | None = None, bot: bool = False, user_id: str | None = None) -> dict:
    return {
        "id": user_id or uuid.uuid4().hex[:12], "name": name[:24] or "Fan", "club_id": club_id,
        "persona": "fan", "lang": "en", "biscuits": START_BISCUITS, "xp": 0, "streak": 0, "best_streak": 0,
        "goldfish_week": None, "calls_total": 0, "calls_won": 0, "calibration_points": 0, "stickers": {},
        "missions": {"date": _today(), "progress": {k: 0 for k in MISSIONS}, "claimed": []},
        "leagues": [DEFAULT_LEAGUE], "bot": bot, "created_at": time.time(),
    }


def daily_top_up(u: dict) -> bool:
    """Broke fans get 300 biscuits once a day, so nobody is locked out of the game."""
    if u["biscuits"] < 50 and u.get("topup_date") != _today():
        u["biscuits"] += 300
        u["topup_date"] = _today()
        return True
    return False


def public_user(u: dict) -> dict:
    m = u["missions"]
    if m.get("date") != _today():
        m = {"date": _today(), "progress": {k: 0 for k in MISSIONS}, "claimed": []}
    return {
        **{k: u[k] for k in ("id", "name", "club_id", "persona", "lang", "biscuits", "xp", "streak",
                             "best_streak", "calls_total", "calls_won", "calibration_points", "leagues")},
        "level": level_for(u["xp"]), "next_level_xp": 50 * level_for(u["xp"]) ** 2,
        "goldfish_available": u.get("goldfish_week") != _iso_week(),
        "stickers": public_stickers(u),
        "missions": [{"id": k, **v, "progress": min(m["progress"].get(k, 0), v["target"]),
                      "done": k in m["claimed"]} for k, v in MISSIONS.items()],
    }


class GameService:
    def __init__(self, store: Store):
        self.store = store

    async def bootstrap(self) -> None:
        """Seed the Diamond Dogs league with a few rival fans so leaderboards feel alive."""
        if await self.store.get_league(DEFAULT_LEAGUE):
            return
        members = []
        rng = random.Random(7)
        for name, _skill in BOTS:
            u = new_user(name, bot=True, user_id=f"bot-{name.lower()}")
            u["biscuits"] = START_BISCUITS + rng.randint(-150, 900)
            u["xp"] = rng.randint(200, 1400)
            await self.store.put_user(u)
            members.append(u["id"])
        await self.store.put_league({"code": DEFAULT_LEAGUE, "name": "Diamond Dogs", "owner": "system",
                                     "members": members})

    # ----------------------------------------------------------------- users
    async def create_user(self, name: str, club_id: str | None) -> dict:
        u = new_user(name, club_id=club_id)
        await self.store.put_user(u)
        league = await self.store.get_league(DEFAULT_LEAGUE)
        if league is not None and u["id"] not in league["members"]:
            league["members"].append(u["id"])
            await self.store.put_league(league)
        return u

    async def update_prefs(self, user_id: str, prefs: dict) -> dict | None:
        u = await self.store.get_user(user_id)
        if not u:
            return None
        for k in ("name", "club_id", "persona", "lang"):
            if k in prefs and prefs[k] is not None:
                u[k] = prefs[k]
        await self.store.put_user(u)
        return u

    def _missions(self, u: dict) -> dict:
        if u["missions"].get("date") != _today():
            u["missions"] = {"date": _today(), "progress": {k: 0 for k in MISSIONS}, "claimed": []}
        return u["missions"]

    def _progress(self, u: dict, key: str, n: int = 1) -> list[dict]:
        m = self._missions(u)
        m["progress"][key] = m["progress"].get(key, 0) + n
        out = []
        if key not in m["claimed"] and m["progress"][key] >= MISSIONS[key]["target"]:
            m["claimed"].append(key)
            u["biscuits"] += MISSIONS[key]["reward"]
            u["xp"] += 40
            out.append({"type": "mission_complete", "mission": key, "label": MISSIONS[key]["label"],
                        "reward": MISSIONS[key]["reward"], "biscuits": u["biscuits"]})
        return out

    async def record_activity(self, user_id: str, kind: str, lang: str | None = None) -> list[dict]:
        u = await self.store.get_user(user_id)
        if not u:
            return []
        out: list[dict] = []
        if kind == "read_story":
            out += self._progress(u, "stories")
            langs = set(u.get("story_langs") or [])
            if lang in ("en", "es", "pt", "fr"):
                langs.add(lang)
                u["story_langs"] = sorted(langs)
            if len(langs) >= 2:
                out += self._sticker(u, "polyglot")
        elif kind == "halftime":
            out += self._sticker(u, "halftime_tea")
        await self.store.put_user(u)
        return out

    async def touched_sign(self, user_id: str, room: MatchRoom, side: int) -> list[dict]:
        """Touching the sign for a side that's behind earns the Believe sticker (the first time)."""
        u = await self.store.get_user(user_id)
        if not u:
            return []
        msgs = self._sticker(u, "believe", f"{room.names[side]}, {room.minute()}'")
        if msgs:
            await self.store.put_user(u)
        return msgs

    async def pay_believers(self, room: MatchRoom, user_ids: list[str], side: int) -> list[tuple[str, dict]]:
        """They drew level: everyone who touched the sign gets the believers' bonus."""
        out = []
        for uid in user_ids:
            u = await self.store.get_user(uid)
            if not u or u.get("bot"):
                continue
            u["biscuits"] += BELIEVE_REWARD
            u["xp"] += 10
            await self.store.put_user(u)
            out.append((uid, {"type": "believe_paid", "match_id": room.match_id, "team": room.names[side],
                              "reward": BELIEVE_REWARD, "biscuits": u["biscuits"]}))
        return out

    async def pay_motm(self, room: MatchRoom, user_ids: list[str], player: str, early: list[str] | None = None,
                       minute: int = 0) -> list[tuple[str, dict]]:
        """Full time: fans who picked the Gaffer's Player of the Match get a bonus and Gaffer's Eye; those
        who picked them before their big moment also get Saw It Coming."""
        out = []
        early_set = set(early or [])
        for uid in user_ids:
            u = await self.store.get_user(uid)
            if not u or u.get("bot"):
                continue
            u["biscuits"] += MOTM_REWARD
            u["xp"] += 5
            msgs = self._sticker(u, "gaffers_eye", f"{player}, {room.names[0]} v {room.names[1]}")
            if uid in early_set:
                msgs += self._sticker(u, "saw_it_coming", f"{player}, before the {minute}' moment")
            await self.store.put_user(u)
            out.append((uid, {"type": "motm_paid", "match_id": room.match_id, "player": player,
                              "reward": MOTM_REWARD, "biscuits": u["biscuits"]}))
            out.extend((uid, m) for m in msgs)
        return out

    async def climbed(self, room: MatchRoom, user_ids: list[str], club_id: str, club: str, places: int,
                      position: int) -> list[tuple[str, dict]]:
        """Full time: fans of a club that climbed three places or more, who took part in the match, get On the Up."""
        out = []
        for uid in user_ids:
            u = await self.store.get_user(uid)
            if not u or u.get("bot") or u.get("club_id") != club_id:
                continue
            msgs = self._sticker(u, "on_the_up", f"{club}, up {places} to {position}")
            if msgs:
                await self.store.put_user(u)
                out.extend((uid, m) for m in msgs)
        return out

    async def simple_sticker(self, user_id: str, key: str, detail: str | None = None) -> list[dict]:
        """A sticker earned by doing something once (Press Pass, All Ears)."""
        u = await self.store.get_user(user_id)
        if not u or u.get("bot"):
            return []
        msgs = self._sticker(u, key, detail)
        if msgs:
            await self.store.put_user(u)
        return msgs

    @staticmethod
    def _sticker(u: dict, key: str, detail: str | None = None) -> list[dict]:
        msg = award(u, key, detail, time.time())
        return [msg] if msg else []

    # ----------------------------------------------------------------- calls
    async def place_call(self, user_id: str, room: MatchRoom, market_id: str, option_id: str, stake: int,
                         confidence: float | None = None) -> tuple[dict | None, str | None, list[dict]]:
        u = await self.store.get_user(user_id)
        if not u:
            return None, "unknown user", []
        m = room.markets.get(market_id)
        if not m or m.status != "open":
            return None, "this call has closed", []
        opt = next((o for o in m.options if o["id"] == option_id), None)
        if not opt:
            return None, "unknown option", []
        if stake not in STAKES:
            return None, "invalid stake", []
        if u["biscuits"] < stake:
            return None, "not enough biscuits", []
        existing = [c for c in await self.store.calls_for_market(market_id) if c["user_id"] == user_id]
        if existing:
            return None, "you already called this one", []
        u["biscuits"] -= stake
        u["calls_total"] += 1
        u["xp"] += 10
        call = {"id": uuid.uuid4().hex[:12], "user_id": user_id, "match_id": room.match_id,
                "market_id": market_id, "question": m.question, "option_id": option_id, "label": opt["label"],
                "stake": stake, "multiplier": opt["multiplier"], "p": opt["p"],
                "confidence": confidence if confidence is not None else None,
                "minute": room.minute(), "status": "open", "payout": 0, "placed_at": time.time(),
                "kind": m.kind, "params": m.params, "score_at_call": list(room.state.goals)}
        msgs: list[dict] = []
        if not u.get("bot"):
            msgs += self._sticker(u, "first_call")
            if m.kind == "comeback" and option_id == "yes":
                msgs += self._sticker(u, "believe", f"{room.names[0]} v {room.names[1]}, {room.minute()}'")
        await self.store.put_call(call)
        await self.store.put_user(u)
        return call, None, msgs

    async def bot_calls(self, room: MatchRoom, m: Market) -> None:
        """Rival fans make their own calls, with a little more skill than chance."""
        rng = random.Random(hash(m.market_id))
        league = await self.store.get_league(DEFAULT_LEAGUE)
        for uid in (league or {}).get("members", []):
            if not uid.startswith("bot-") or rng.random() < 0.55:
                continue
            bot = await self.store.get_user(uid)
            if bot and bot["biscuits"] < 300:  # rivals get a top-up, so the table stays competitive
                bot["biscuits"] += 600
                await self.store.put_user(bot)
            ps = [o["p"] for o in m.options]
            weights = [p ** 1.3 for p in ps]
            opt = rng.choices(m.options, weights=weights)[0]
            await self.place_call(uid, room, m.market_id, opt["id"], rng.choice(STAKES))  # bots earn no stickers

    async def settle(self, room: MatchRoom, m: Market) -> list[tuple[str, dict]]:
        """Settle every call on a market. Returns (user_id, message) pairs to push."""
        out: list[tuple[str, dict]] = []
        for call in await self.store.calls_for_market(m.market_id):
            if call["status"] != "open":
                continue
            u = await self.store.get_user(call["user_id"])
            if not u:
                continue
            won = call["option_id"] == m.result
            msgs: list[dict] = []
            if won:
                bonus = streak_bonus(u["streak"])
                payout = int(round(call["stake"] * call["multiplier"] * bonus))
                call.update(status="won", payout=payout, streak_bonus=bonus)
                u["biscuits"] += payout
                u["calls_won"] += 1
                u["streak"] += 1
                u["best_streak"] = max(u["best_streak"], u["streak"])
                u["xp"] += 25
                if not u.get("bot"):
                    msgs += await self._stickers_for_win(u, call, m, room)
                msgs += self._progress(u, "correct_calls")
                if call["p"] < 0.25:
                    msgs += self._progress(u, "underdog")
            else:
                call.update(status="lost", payout=0)
                runs = u.setdefault("match_runs", {})
                runs[room.match_id] = 0
                if u["streak"] >= 3 and u.get("goldfish_week") != _iso_week():
                    u["goldfish_week"] = _iso_week()
                    u["goldfish_pending"] = True
                    call["goldfish"] = True
                    msgs.append({"type": "goldfish", "streak": u["streak"],
                                 "text": "Goldfish: that miss is forgotten and your streak lives on."})
                else:
                    u["streak"] = 0
                    u["goldfish_pending"] = False
            conf = call.get("confidence")
            if conf is not None:
                u["calibration_points"] += calibration_points(won, conf)
            call["result"] = m.result
            call["settled_at"] = time.time()
            await self.store.put_call(call)
            await self.store.put_user(u)
            if not u.get("bot"):
                out.append((u["id"], {"type": "call_settled", "call": call, "user": public_user(u)}))
                out.extend((u["id"], msg) for msg in msgs)
        return out

    async def _stickers_for_win(self, u: dict, call: dict, m: Market, room: MatchRoom) -> list[dict]:
        """Which stickers this winning call earns. Every rule uses facts the game already knows."""
        match = f"{room.names[0]} v {room.names[1]}"
        where = f"{match}, {room.minute()}'"
        out = self._sticker(u, "called_it", where)
        p, kind = call["p"], m.kind
        if p < 0.25:
            out += self._sticker(u, "underdog", f"{call['label']} at {round(p * 100)}%, {match}")
        if p < 0.10:
            out += self._sticker(u, "long_shot", f"{call['label']} at {round(p * 100)}%, {match}")
        if u["streak"] >= 5:
            out += self._sticker(u, "on_fire")
        if u["streak"] >= 10:
            out += self._sticker(u, "unstoppable")
        if u["calls_won"] >= 10:
            out += self._sticker(u, "sharp_eye")
        runs = u.setdefault("match_runs", {})
        runs[room.match_id] = runs.get(room.match_id, 0) + 1
        if runs[room.match_id] >= 3:
            out += self._sticker(u, "hat_trick", match)
        if u.get("goldfish_pending"):
            u["goldfish_pending"] = False
            out += self._sticker(u, "goldfish")
        # Goal calls: which side scored, if this was a call on a goal.
        scorer: int | None = None
        if kind == "score" and m.result == "yes":
            scorer = int(m.market_id.split(":")[-1].split("-")[1])
        elif kind == "next" and m.result in ("home", "away"):
            scorer = 0 if m.result == "home" else 1
        if scorer is not None:
            if room.minute() >= 80:
                out += self._sticker(u, "rom_com", where)
            if room.state.reds[scorer] > 0:
                out += self._sticker(u, "ten_men", where)
        if kind == "var":
            out += self._sticker(u, "var_whisperer", f"{call['label']}, {where}")
        if kind == "comeback" and call["option_id"] == "yes":
            out += self._sticker(u, "comeback", match)
        if kind == "result" and call["minute"] <= 10:
            out += self._sticker(u, "bullseye", f"{call['label']}, called at {call['minute']}'")
        league = await self.store.get_league(DEFAULT_LEAGUE)
        if league and u["id"] in league["members"]:
            others = [x for uid in league["members"] if uid != u["id"] and (x := await self.store.get_user(uid))]
            if others and u["biscuits"] > max(x["biscuits"] for x in others):
                out += self._sticker(u, "diamond_dog")
        return out

    # --------------------------------------------------------------- leagues
    async def create_league(self, user_id: str, name: str) -> dict:
        code = secrets.token_hex(3).upper()
        league = {"code": code, "name": name[:32] or "My league", "owner": user_id, "members": [user_id]}
        await self.store.put_league(league)
        u = await self.store.get_user(user_id)
        if u:
            u["leagues"] = list(dict.fromkeys([*u["leagues"], code]))
            await self.store.put_user(u)
        return league

    async def join_league(self, user_id: str, code: str) -> dict | None:
        league = await self.store.get_league(code.upper())
        if not league:
            return None
        if user_id not in league["members"]:
            league["members"].append(user_id)
            await self.store.put_league(league)
        u = await self.store.get_user(user_id)
        if u:
            u["leagues"] = list(dict.fromkeys([*u["leagues"], league["code"]]))
            await self.store.put_user(u)
        return league

    async def leaderboard(self, code: str | None = None) -> dict:
        if code:
            league = await self.store.get_league(code.upper())
            if not league:
                return {"code": code, "name": "", "rows": []}
            users = [u for uid in league["members"] if (u := await self.store.get_user(uid))]
            name = league["name"]
        else:
            users, name = await self.store.list_users(), "Global"
        users.sort(key=lambda u: u["biscuits"], reverse=True)
        rows = [{"rank": i + 1, "id": u["id"], "name": u["name"], "biscuits": u["biscuits"],
                 "streak": u["streak"], "level": level_for(u["xp"])} for i, u in enumerate(users[:50])]
        return {"code": code, "name": name, "rows": rows}
