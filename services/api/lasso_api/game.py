"""Beat the Gaffer: calls, biscuits, streaks, the Goldfish, moment cards, missions and leagues."""

from __future__ import annotations

import datetime as dt
import math
import random
import secrets
import time
import uuid

from lasso_engine.markets import calibration_points

from .matchroom import Market, MatchRoom
from .store import Store

START_BISCUITS = 1000
STAKES = (50, 100, 250)
MISSIONS = {
    "correct_calls": {"target": 3, "reward": 150, "label": "Call 3 moments correctly"},
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
        "goldfish_week": None, "calls_total": 0, "calls_won": 0, "calibration_points": 0, "cards": [],
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
        "cards": u["cards"][-30:],
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
                        "reward": MISSIONS[key]["reward"]})
        return out

    async def record_activity(self, user_id: str, kind: str) -> list[dict]:
        u = await self.store.get_user(user_id)
        if not u or kind != "read_story":
            return []
        out = self._progress(u, "stories")
        await self.store.put_user(u)
        return out

    # ----------------------------------------------------------------- calls
    async def place_call(self, user_id: str, room: MatchRoom, market_id: str, option_id: str, stake: int,
                         confidence: float | None = None) -> tuple[dict | None, str | None]:
        u = await self.store.get_user(user_id)
        if not u:
            return None, "unknown user"
        m = room.markets.get(market_id)
        if not m or m.status != "open":
            return None, "this call has closed"
        opt = next((o for o in m.options if o["id"] == option_id), None)
        if not opt:
            return None, "unknown option"
        if stake not in STAKES:
            return None, "invalid stake"
        if u["biscuits"] < stake:
            return None, "not enough biscuits"
        existing = [c for c in await self.store.calls_for_market(market_id) if c["user_id"] == user_id]
        if existing:
            return None, "you already called this one"
        u["biscuits"] -= stake
        u["calls_total"] += 1
        u["xp"] += 10
        call = {"id": uuid.uuid4().hex[:12], "user_id": user_id, "match_id": room.match_id,
                "market_id": market_id, "question": m.question, "option_id": option_id, "label": opt["label"],
                "stake": stake, "multiplier": opt["multiplier"], "p": opt["p"],
                "confidence": confidence if confidence is not None else None,
                "minute": room.minute(), "status": "open", "payout": 0, "placed_at": time.time()}
        await self.store.put_call(call)
        await self.store.put_user(u)
        return call, None

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
            await self.place_call(uid, room, m.market_id, opt["id"], rng.choice(STAKES))

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
                card = self._card_for(call, room)
                if card:
                    u["cards"].append(card)
                    msgs.append({"type": "card", "card": card})
                msgs += self._progress(u, "correct_calls")
                if call["p"] < 0.25:
                    msgs += self._progress(u, "underdog")
            else:
                call.update(status="lost", payout=0)
                if u["streak"] >= 3 and u.get("goldfish_week") != _iso_week():
                    u["goldfish_week"] = _iso_week()
                    call["goldfish"] = True
                    msgs.append({"type": "goldfish", "streak": u["streak"],
                                 "text": "Be a goldfish. Your streak survives this one."})
                else:
                    u["streak"] = 0
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

    def _card_for(self, call: dict, room: MatchRoom) -> dict | None:
        p = call["p"]
        rarity = "gold" if p < 0.10 else "silver" if p < 0.25 else "bronze" if p < 0.5 else None
        if not rarity:
            return None
        return {"id": call["id"], "rarity": rarity, "title": call["question"], "pick": call["label"],
                "p": p, "minute": call["minute"], "match": f"{room.names[0]} v {room.names[1]}",
                "score": list(room.state.goals), "earned_at": time.time()}

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
