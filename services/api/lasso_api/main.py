"""Lasso API: live match rooms, the Gaffer's MCP server, the game, and realtime fan-out."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import time
import uuid
from collections import OrderedDict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from lasso_engine.markets import generate_markets

from .agents_client import AgentsClient
from .config import settings
from .data import DemoData
from .feed import Scheduler, consume_forever, replay
from .game import STAKES, GameService, daily_top_up, public_user
from .matchroom import MatchRoom
from . import season as season_mod
from .mcp_tools import build_mcp
from .speech import Speech
from .realtime import LocalHub, make_hub
from .store import make_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("lasso.api")
if os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor()

data = DemoData(settings.data_dir)
rooms: dict[str, MatchRoom] = {mid: MatchRoom(mid, data) for mid in settings.featured_matches
                               if mid in data.matches}
hub = make_hub(settings.webpubsub_endpoint, settings.webpubsub_hub, settings.managed_identity_client_id)
store = make_store(settings.cosmos_endpoint, settings.cosmos_database, settings.managed_identity_client_id)
game = GameService(store)
agents = AgentsClient(settings.agents_url, settings.agents_timeout) if settings.agents_url else None
mcp = build_mcp(rooms)
speech = Speech(settings.speech_region, settings.speech_resource_id, settings.managed_identity_client_id,
                settings.speech_daily_limit)
scheduler = Scheduler(data, lambda mid, ev: on_event(mid, ev))
_last_stats: dict[str, float] = {}
_background: set[asyncio.Task] = set()
# Event Hubs health: if the hub stays quiet, the API plays the matches itself so the live demo never goes dark.
_feed = {"fallback": False, "last_event": 0.0, "started": time.monotonic()}


def _spawn(coro) -> None:
    t = asyncio.create_task(coro)
    _background.add(t)
    t.add_done_callback(_background.discard)


# ------------------------------------------------------------------ pipeline
async def on_event(match_id: str, ev: dict) -> None:
    room = rooms.get(match_id)
    if room is None:
        room = rooms[match_id] = MatchRoom(match_id, data)
        _spawn(_warm_season([match_id]))
    if ev.get("type") == "match_reset":
        room.reset()
        await hub.to_group(f"match:{match_id}", {"type": "reset", "match": room.summary()})
        for msg in room._season_msg():
            await hub.to_group(f"match:{match_id}", msg)
        await hub.to_group("lobby", {"type": "status", "match": room.summary()})
        return
    seq = int(ev.get("seq") or 0)
    if seq and seq <= room.last_seq:
        return  # already applied (a duplicate delivery)
    if seq > room.last_seq + 1:
        n = room.catch_up(seq)
        if n:
            log.info("caught up %s: replayed %d missed events before seq %d", match_id, n, seq)
            await hub.to_group(f"match:{match_id}", {"type": "reset", "match": room.summary()})
    for msg in room.ingest(ev):
        await publish(room, msg)
    now = time.time()
    if now - _last_stats.get(match_id, 0) > 4:
        _last_stats[match_id] = now
        await hub.to_group(f"match:{match_id}", {"type": "stats", "stats": room.stats_public()})


async def publish(room: MatchRoom, msg: dict) -> None:
    group = f"match:{room.match_id}"
    kind = msg["type"]
    if kind == "believe_result":  # pay the believers privately; tell the room without the list of fans
        if msg["users"]:
            _spawn(pay_believers(room, msg["users"], msg["side"]))
        await hub.to_group(group, {k: v for k, v in msg.items() if k != "users"} | {"type": "believe"})
        return
    await hub.to_group(group, msg)
    if kind in ("status", "meter"):
        if kind == "status" or int(time.time()) % 3 == 0:
            await hub.to_group("lobby", {"type": "status", "match": room.summary()})
    elif kind == "market_open":
        _spawn(game.bot_calls(room, room.markets[msg["market"]["market_id"]]))
    elif kind == "market_settled":
        _spawn(settle(room, msg["market"]["market_id"]))
    elif kind == "moment" and agents is not None and await _should_enrich(room, msg["moment"]):
        _spawn(enrich(room, msg["moment"]))


_enrich_state = {"day": "", "count": 0, "last": {}}
_forced_agents: set[str] = set()  # matches replayed with agents on even with no live viewers (the evaluation)
ALWAYS_ENRICH = {"goal", "red_card", "half_time", "full_time", "var_overturned"}


async def _should_enrich(room: MatchRoom, moment: dict) -> bool:
    """Cost guard-rails: agents only run for matches people are watching, with a per-match gap and daily cap."""
    day = time.strftime("%Y-%m-%d")
    if _enrich_state["day"] != day:
        _enrich_state.update(day=day, count=0)
    if _enrich_state["count"] >= settings.agents_daily_limit:
        return False
    if moment["trigger"] == "kickoff":  # the template says it well; save the agents for real moments
        return False
    if room.match_id in _forced_agents:
        if moment["trigger"] == "full_time":
            _forced_agents.discard(room.match_id)
    elif not await hub.has_viewers(f"match:{room.match_id}"):
        return False
    last = _enrich_state["last"].get(room.match_id, 0.0)
    if moment["trigger"] not in ALWAYS_ENRICH and time.time() - last < settings.agents_min_gap_seconds:
        return False
    _enrich_state["last"][room.match_id] = time.time()
    _enrich_state["count"] += 1
    return True


async def pay_believers(room: MatchRoom, users: list[str], side: int) -> None:
    for user_id, msg in await game.pay_believers(room, users, side):
        await hub.to_user(user_id, msg)


async def settle(room: MatchRoom, market_id: str) -> None:
    for user_id, msg in await game.settle(room, room.markets[market_id]):
        await hub.to_user(user_id, msg)


_DASHES = re.compile(r"\s*[\u2014\u2013]\s*")


def _clean(text: object) -> str:
    """House style for model text: no em or en dashes, trimmed."""
    return _DASHES.sub(", ", str(text)).strip()


_US = {"favourite": "favorite", "equaliser": "equalizer", "equalise": "equalize", "defence": "defense",
       "colour": "color", "centre": "center", "honour": "honor", "organise": "organize", "realise": "realize",
       "neighbour": "neighbor", "behaviour": "behavior", "offence": "offense", "programme": "program"}
_US_RE = re.compile(r"\b(" + "|".join(_US) + r")", re.IGNORECASE)
_FROM_TO = re.compile(r"\bfrom (\d+) ?% to (\d+) ?%")
_FROM_TO_LANG = {"es": "del {}% al {}%", "pt": "de {}% para {}%", "fr": "de {} % à {} %"}
# What models still slip into despite instructions: European Portuguese, and English "chances" in Spanish.
_FIXES = {
    "pt": [(r"\bgolos\b", "gols"), (r"\bgolo\b", "gol"), (r"\bequipas\b", "times"), (r"\bequipa\b", "time"),
           (r"\bremates\b", "chutes"), (r"\bremate\b", "chute"), (r"\ba jogar\b", "jogando"),
           (r"\ba correr\b", "correndo"), (r"\ba ganhar\b", "ganhando"), (r"\ba perder\b", "perdendo"),
           (r"\ba pressionar\b", "pressionando"), (r"(\d+)\.º", r"\1º")],
    "es": [(r"\bchances\b", "opciones"), (r"\buna chance\b", "una opción"), (r"\bchance\b", "opción"),
           (r"\bpossession\b", "posesión")],
}


def _us(m: re.Match) -> str:
    word = _US[m.group(1).lower()]
    return word.capitalize() if m.group(1)[0].isupper() else word


def _localize(lang: str, text: str) -> str:
    """Deterministic fixes for what models still slip on: US spelling, and English left in translations."""
    if lang == "en":
        return _US_RE.sub(_us, text)
    if fmt := _FROM_TO_LANG.get(lang):
        text = _FROM_TO.sub(lambda m: fmt.format(m.group(1), m.group(2)), text)
    for pat, rep in _FIXES.get(lang, []):
        text = re.sub(pat, lambda m, r=rep: _same_case(m.group(0), m.expand(r)), text, flags=re.IGNORECASE)
    return text


def _same_case(old: str, new: str) -> str:
    return new[:1].upper() + new[1:] if old[:1].isupper() else new


def _lang_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {k: _localize(k, _clean(v)) for k, v in value.items()
            if k in ("en", "es", "pt", "fr") and isinstance(v, str) and v.strip()}


def _pct(p: dict) -> dict:
    return {k: round(100 * float(v)) for k, v in p.items()}


async def enrich(room: MatchRoom, moment: dict) -> None:
    """Ask the Match Director (five agents) for a richer package; merge it in when it arrives."""
    side = "home" if moment["focus"] == 0 else "away"
    brief = {k: moment[k] for k in ("moment_id", "match_id", "trigger", "minute", "score")}
    brief["teams"] = list(room.names)
    brief["focus_team"] = room.names[moment["focus"]]
    h, a = moment["score"]
    brief["score_text"] = f"{room.names[0]} {h}-{a} {room.names[1]}"
    reds = list(room.state.reds)
    if any(reds):
        brief["red_cards"] = {room.names[0]: reds[0], room.names[1]: reds[1]}
    brief["before_pct"], brief["after_pct"] = _pct(moment["before"]), _pct(moment["after"])
    brief["focus_change"] = f"{brief['before_pct'][side]}% to {brief['after_pct'][side]}%"
    brief["drivers"] = [{"label": d["label"]["en"], "points": round(float(d["delta"]), 1)}
                        for d in moment["drivers"]]
    if moment.get("var"):  # a goal that survived a VAR check, or one VAR ruled out
        brief["var"] = moment["var"]
    if moment.get("season"):  # full time: what the result did to the season of the club with most at stake
        ss = moment["season"]
        brief["season"] = {"club": ss["club"], "race": season_mod.ZONE_WORDS[ss["zone"]],
                           "chance_before_kickoff_pct": ss["was_pct"], "chance_now_pct": ss["now_pct"]}
    t0 = time.time()
    pkg = await agents.produce(brief)
    # A real package echoes our moment id and carries the agents' trace; anything else is an error reply.
    if not pkg or pkg.get("moment_id") != moment["moment_id"] or not pkg.get("trace"):
        if pkg:
            log.warning("agents returned no package for %s; keeping template narration", moment["moment_id"])
        return
    # The story is only labeled as the agents' when they wrote its words (a narrator timeout leaves the
    # template text, even if the persona's analyst view and club lines arrived).
    applied = False
    for key in ("headline", "story", "analyst"):
        if vals := _lang_map(pkg.get(key)):
            moment[key] = {**moment.get(key, {}), **vals}
            applied = applied or key in ("headline", "story")
    lines = pkg.get("club_lines") if isinstance(pkg.get("club_lines"), dict) else {}
    for s_ in ("home", "away"):
        if vals := _lang_map(lines.get(s_)):
            moment.setdefault("club_lines", {})[s_] = {**moment.get("club_lines", {}).get(s_, {}), **vals}
    moment["agent_trace"] = pkg.get("trace", [])
    moment["latency_ms"] = int((time.time() - t0) * 1000)
    if applied:
        moment["source"] = "agents"
    await hub.to_group(f"match:{room.match_id}", {"type": "moment_update", "moment": moment})
    challenge = pkg.get("challenge") or {}
    if challenge.get("market_id") and room.status == "live":
        cands = {c.market_id: c for c in generate_markets(room.gaffer, room.state, *room.names)}
        cand = cands.get(challenge["market_id"])
        open_kinds = {m.kind for m in room.markets.values() if m.status == "open"}
        if cand and cand.market_id.split("-")[0] not in open_kinds and len(open_kinds) < 2:
            copy = challenge.get("copy")
            copy = _lang_map(copy) if isinstance(copy, dict) else ({"en": _clean(copy)[:140]} if copy else None)
            for msg in room.open_market(cand, copy=copy or None):
                await publish(room, msg)


_overrides: set[str] = set()  # matches temporarily replayed locally (demo recording), ignoring Event Hubs


async def on_hub_event(match_id: str, ev: dict) -> None:
    if not _feed["fallback"] and match_id not in _overrides:
        await on_event(match_id, ev)


def _hub_heard() -> None:
    _feed["last_event"] = time.monotonic()


async def _feed_watchdog() -> None:
    while not _feed["fallback"]:
        await asyncio.sleep(15)
        quiet = time.monotonic() - (_feed["last_event"] or _feed["started"])
        if quiet > settings.feed_fallback_seconds:
            log.warning("No Event Hubs events for %.0fs: falling back to the in-process match feed", quiet)
            _feed["fallback"] = True
            scheduler.start()


async def _warm_season(match_ids: list[str]) -> None:
    """Simulate the rest of the season for these matches in a worker thread, then tell anyone watching."""
    await season_mod.warm(data, match_ids)
    for mid in match_ids:
        room = rooms.get(mid)
        if room is not None:
            for msg in room._season_msg():
                await hub.to_group(f"match:{mid}", msg)
            await hub.to_group("lobby", {"type": "status", "match": room.summary()})


# ------------------------------------------------------------------- app
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    await game.bootstrap()
    async with mcp.session_manager.run():
        if settings.event_source == "eventhubs":
            _spawn(consume_forever(on_hub_event, on_received=_hub_heard))
            if settings.feed_fallback_seconds > 0:
                _spawn(_feed_watchdog())
        else:
            scheduler.start()
        _spawn(_warm_season(list(rooms)))
        log.info("Lasso API ready: %d featured matches, agents=%s", len(rooms), bool(agents))
        yield


app = FastAPI(title="Lasso API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/mcp", mcp.streamable_http_app())


class NewUser(BaseModel):
    name: str = Field("Fan", max_length=24)
    club_id: str | None = None


class Prefs(BaseModel):
    name: str | None = Field(None, max_length=24)
    club_id: str | None = None
    persona: str | None = Field(None, pattern="^(fan|analyst)$")
    lang: str | None = Field(None, pattern="^(en|es|pt|fr)$")


class NewCall(BaseModel):
    user_id: str
    market_id: str
    option_id: str
    stake: int
    confidence: float | None = Field(None, ge=0.5, le=1.0)


class AskIn(BaseModel):
    user_id: str = Field(..., max_length=40)
    question: str = Field(..., min_length=3, max_length=200)
    lang: str | None = Field(None, pattern="^(en|es|pt|fr)$")


class BelieveIn(BaseModel):
    user_id: str = Field(..., max_length=40)
    side: int = Field(..., ge=0, le=1)


class SpeechIn(BaseModel):
    kind: str = Field(..., pattern="^(story|answer)$")
    id: str = Field(..., max_length=80)
    lang: str = Field("en", pattern="^(en|es|pt|fr)$")
    match_id: str | None = Field(None, max_length=40)


class LeagueIn(BaseModel):
    user_id: str
    name: str | None = None
    code: str | None = None


@app.get("/api/health")
async def health() -> dict:
    if settings.event_source != "eventhubs":
        feed = "local"
    else:
        feed = "local-fallback" if _feed["fallback"] else "eventhubs"
    last = round(time.monotonic() - _feed["last_event"], 1) if _feed["last_event"] else None
    return {"ok": True, "matches": len(rooms), "agents": bool(agents), "model": data.model_meta.get("version"),
            "agent_calls_today": _enrich_state["count"], "asks_today": _ask_state["count"], "feed": feed,
            "seconds_since_hub_event": last}


@app.get("/api/negotiate")
async def negotiate(request: Request, user_id: str = Query(..., max_length=40)) -> dict:
    scheme = "wss" if request.headers.get("x-forwarded-proto", request.url.scheme) == "https" else "ws"
    host = request.headers.get("x-forwarded-host", request.url.netloc)
    return await hub.negotiate(user_id, f"{scheme}://{host}")


@app.websocket("/ws")
async def ws(websocket: WebSocket, user_id: str = "anon") -> None:
    if not isinstance(hub, LocalHub):
        await websocket.close(code=4000)
        return
    await hub.serve(websocket, user_id)


@app.get("/api/clubs")
async def clubs() -> list[dict]:
    return [{k: c[k] for k in ("club_id", "name", "short", "monogram", "primary", "secondary")}
            for c in data.clubs.values()]


@app.get("/api/matches")
async def matches() -> list[dict]:
    order = {"live": 0, "half_time": 0, "scheduled": 1, "finished": 2}
    return sorted((r.summary() for r in rooms.values()), key=lambda m: order.get(m["status"], 3))


@app.get("/api/matches/{match_id}")
async def match(match_id: str) -> dict:
    if match_id not in rooms:
        raise HTTPException(404, "match not found")
    return rooms[match_id].snapshot()


@app.get("/api/matches/{match_id}/season")
async def match_season(match_id: str) -> dict:
    """The season outlook for this match: the table as it stands and what the result means for each club."""
    if match_id not in rooms:
        raise HTTPException(404, "match not found")
    view = rooms[match_id].season_tool()
    if view is None:
        await asyncio.to_thread(season_mod.compute, data, match_id)
        view = rooms[match_id].season_tool()
    return view or {}


@app.get("/api/matches/{match_id}/story")
async def match_story(match_id: str) -> list[dict]:
    """Every story published in this match so far, oldest first (the snapshot only carries the latest few)."""
    if match_id not in rooms:
        raise HTTPException(404, "match not found")
    return [{k: v for k, v in m.items() if k != "window"} for m in rooms[match_id].moments]


@app.get("/api/speech")
async def speech_status() -> dict:
    """Whether the server reads aloud with Azure AI Speech; if not, the app uses the phone's voice."""
    return {"azure": speech.enabled}


@app.get("/api/speech/audio")
async def listen(kind: str = Query(..., pattern="^(story|answer)$"), id: str = Query(..., max_length=80),
                 lang: str = Query("en", pattern="^(en|es|pt|fr)$"),
                 match_id: str | None = Query(None, max_length=40)) -> Response:
    """Listen: a story or a Gaffer answer read aloud in the fan's language (MP3). The text comes from the server,
    never from the request, so this can't be used to read arbitrary text. It's a plain GET so a phone can start
    playing it inside the tap (iPhones block audio started later)."""
    body = SpeechIn(kind=kind, id=id, lang=lang, match_id=match_id)
    if body.kind == "story":
        room = rooms.get(body.match_id or "")
        m = next((x for x in (room.moments if room else []) if x["moment_id"] == body.id), None)
        if m is None:
            raise HTTPException(404, "story not found")
        head = ((m.get("headline") or {}).get(body.lang) or "").strip()
        if head and head[-1] not in ".!?":
            head += "."  # a pause between the headline and the story
        text = f"{head} {(m.get('story') or {}).get(body.lang) or ''}".strip()
        lang = body.lang
    else:
        if body.id not in _answers:
            raise HTTPException(404, "answer not found")
        lang, text = _answers[body.id]
    audio = await speech.synthesize(text, lang)
    if audio is None:
        raise HTTPException(503, "speech unavailable")
    return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=86400"})


@app.post("/api/matches/{match_id}/believe")
async def touch_the_sign(match_id: str, body: BelieveIn) -> dict:
    """Touch the sign: believe in a side that's behind. If they draw level, believers get a bonus."""
    room = rooms.get(match_id)
    if room is None:
        raise HTTPException(404, "match not found")
    if not await store.get_user(body.user_id):
        raise HTTPException(404, "user not found")
    r = room.touch_sign(body.user_id, body.side)
    if r is None:
        raise HTTPException(409, "not_behind")
    msgs = await game.touched_sign(body.user_id, room, body.side) if r["new"] else []
    for m in msgs:
        await hub.to_user(body.user_id, m)
    return {**r, "events": msgs}


# ------------------------------------------------------------ Ask the Gaffer
_ask_state: dict = {"day": "", "count": 0, "users": {}}
_answers: "OrderedDict[str, tuple[str, str]]" = OrderedDict()  # ask_id -> (lang, answer), for Listen
KEY_EVENTS = {"goal", "red_card", "yellow_card", "substitution", "half_time"}
_ASK_OFF_TOPIC = {
    "en": "I only talk about this match, so I'll leave that one. Right now at {m}': {score}. My numbers: {h} {ph}%, "
          "draw {pd}%, {a} {pa}%.",
    "es": "Solo hablo de este partido, así que esa la dejo pasar. Ahora, en el minuto {m}: {score}. Mis números: {h} "
          "{ph}%, empate {pd}%, {a} {pa}%.",
    "pt": "Eu só falo deste jogo, então vou deixar essa passar. Agora, aos {m}': {score}. Meus números: {h} {ph}%, "
          "empate {pd}%, {a} {pa}%.",
    "fr": "Je ne parle que de ce match, alors je laisse celle-là. À la {m}e minute : {score}. Mes chiffres : {h} "
          "{ph} %, nul {pd} %, {a} {pa} %.",
}
_ASK_FALLBACK = {
    "en": "I can't take questions right now, but here's where it stands at {m}': {score}. My numbers: {h} {ph}%, "
          "draw {pd}%, {a} {pa}%.",
    "es": "Ahora no puedo responder preguntas, pero así está en el minuto {m}: {score}. Mis números: {h} {ph}%, "
          "empate {pd}%, {a} {pa}%.",
    "pt": "Não consigo responder perguntas agora, mas o jogo está assim aos {m}': {score}. Meus números: {h} "
          "{ph}%, empate {pd}%, {a} {pa}%.",
    "fr": "Je ne peux pas répondre pour l'instant, mais voici le match à la {m}e minute : {score}. Mes chiffres : "
          "{h} {ph} %, nul {pd} %, {a} {pa} %.",
}


_SENTENCE = re.compile(r"(?<=[.!?])\s+")


_XG = re.compile(r"\bxG\b|\d[.,]\d\d")
# An xG phrase inside a sentence: "and 0.68 xG by 48'", "y 0.63 xG acumulado", "(1.26 xG)".
_XG_CLAUSE = re.compile(
    r"\s*\(\s*\d+[.,]\d+\s*xG\s*\)"  # "(1.26 xG)"
    r"|,?\s+\b(?:and|with|y|con|e|com|et|avec)\s+\d+[.,]\d+\s*xG\b"  # "and 0.68 xG", "y 0.63 xG"
    r"(?:\s+(?:by|at|al|aos|à|en|em|in|acumulad[oa]s?|total|so far|until)\b[^,.;)]*)?",
    re.IGNORECASE)


def _plain_for_fans(text: str) -> str:
    """Fans don't get xG decimals: cut the xG phrase out of a sentence, and drop any sentence still quoting
    it as long as another sentence remains."""
    text = _XG_CLAUSE.sub("", text).strip()
    sents = _SENTENCE.split(text)
    keep = [s_ for s_ in sents if not _XG.search(s_)]
    return " ".join(keep) if keep else text


def _cap_words(text: str, limit: int) -> str:
    """Backstop for long answers: keep whole sentences up to the word limit (always at least the first)."""
    out: list[str] = []
    n = 0
    for sent in _SENTENCE.split(text.strip()):
        w = len(sent.split())
        if out and n + w > limit:
            break
        out.append(sent)
        n += w
    return " ".join(out)[:700]


def _ask_allowed(user_id: str) -> str | None:
    """Cost guard-rails for questions: a shared daily cap, and a pace and daily allowance per fan."""
    day = time.strftime("%Y-%m-%d")
    if _ask_state["day"] != day:
        _ask_state.update(day=day, count=0, users={})
    if _ask_state["count"] >= settings.asks_daily_limit:
        return "busy"
    mine = _ask_state["users"].setdefault(user_id, {"n": 0, "last": 0.0})
    if mine["n"] >= settings.asks_per_user_daily:
        return "daily_limit"
    if time.time() - mine["last"] < settings.asks_min_gap_seconds:
        return "slow_down"
    mine["n"] += 1
    mine["last"] = time.time()
    _ask_state["count"] += 1
    return None


def _ask_fallback(room: MatchRoom, lang: str, templates: dict | None = None) -> str:
    p = _pct(room.probs())
    h, a = room.state.goals
    templates = templates or _ASK_FALLBACK
    return templates.get(lang, templates["en"]).format(
        m=room.minute(), score=f"{room.names[0]} {h}-{a} {room.names[1]}", h=room.names[0], a=room.names[1],
        ph=p["home"], pd=p["draw"], pa=p["away"])


@app.post("/api/matches/{match_id}/ask")
async def ask(match_id: str, body: AskIn) -> dict:
    """Ask the Gaffer: a fan's question goes over A2A to the Press Room (the Scout researches it with the
    Gaffer's MCP tools, the Gaffer answers in the fan's language). Only the asker sees the answer."""
    room = rooms.get(match_id)
    if room is None:
        raise HTTPException(404, "match not found")
    u = await store.get_user(body.user_id)
    if not u:
        raise HTTPException(404, "user not found")
    if err := _ask_allowed(body.user_id):
        raise HTTPException(429, err)
    lang = body.lang or u.get("lang") or "en"
    question = _clean(body.question)[:200]
    ask_id = uuid.uuid4().hex[:12]
    t0 = time.time()
    answer, followups, trace, source = "", [], [], "gaffer"
    if agents is not None:
        h, a = room.state.goals
        side = 0 if u.get("club_id") == room.home_id else 1 if u.get("club_id") == room.away_id else None
        p = _pct(room.probs())
        brief = {"kind": "ask", "ask_id": ask_id, "match_id": match_id, "question": question, "lang": lang,
                 "version": u.get("persona") or "fan", "fan_of": room.names[side] if side is not None else None,
                 "status": room.status, "minute": room.minute(), "teams": list(room.names),
                 "score_text": f"{room.names[0]} {h}-{a} {room.names[1]}",
                 "chances_pct": {room.names[0]: p["home"], "draw": p["draw"], room.names[1]: p["away"]}}
        if any(room.state.reds):
            brief["red_cards"] = {room.names[0]: room.state.reds[0], room.names[1]: room.state.reds[1]}
        # The authoritative timeline and numbers, so basic questions never depend on which tools the Scout picks
        # and the Gaffer never has to guess a figure.
        brief["key_events"] = [f"{e['minute']}' {e['text']}" for e in room.feed
                               if e.get("type") in KEY_EVENTS][-24:]
        st = room.stats_public()["teams"]
        fan = (u.get("persona") or "fan") != "analyst"
        brief["numbers"] = {room.names[i]: {**({} if fan else {"xg": st[i]["xg"]}), "shots": st[i]["shots"],
                                            "on_target": st[i]["on_target"], "possession_pct": st[i]["possession"]}
                            for i in (0, 1)}
        sent_off = [f"{c['p']} ({room.names[c['k']]}, {c['m']}')" for c in room.cards if c["c"] == "r"]
        if sent_off:
            brief["sent_off"] = sent_off
            brief["rules"] = ("A sent-off player cannot be replaced by a substitute; that team plays the rest of "
                              "the match a man short.")
        pkg = await agents.produce(brief)
        # A real answer echoes our id and carries the agents' trace; anything else is an error reply.
        if pkg and pkg.get("ask_id") == ask_id and pkg.get("trace") and isinstance(pkg.get("answer"), str):
            answer = _localize(lang, _clean(pkg["answer"]))
            if u.get("persona") != "analyst":
                answer = _plain_for_fans(answer)
            answer = _cap_words(answer, 85 if u.get("persona") == "analyst" else 55)
            followups = [_localize(lang, _clean(f))[:60] for f in (pkg.get("followups") or [])
                         if isinstance(f, str) and f.strip()][:2]
            trace = pkg["trace"]
            source = "agents" if answer else "gaffer"
            if pkg.get("off_topic"):  # the Scout ruled it off topic: a kind fixed reply, with the match situation
                answer, source = _ask_fallback(room, lang, _ASK_OFF_TOPIC), "agents"
    if not answer:
        answer = _ask_fallback(room, lang)
    log.info("ask %s %s source=%s %dms", match_id, ask_id, source, int((time.time() - t0) * 1000))
    _answers[ask_id] = (lang, answer)
    while len(_answers) > 1000:
        _answers.popitem(last=False)
    return {"ask_id": ask_id, "question": question, "answer": answer, "followups": followups, "source": source,
            "trace": trace, "minute": room.minute(), "latency_ms": int((time.time() - t0) * 1000)}


@app.post("/api/users")
async def create_user(body: NewUser) -> dict:
    return public_user(await game.create_user(body.name, body.club_id))


@app.get("/api/users/{user_id}")
async def get_user(user_id: str) -> dict:
    u = await store.get_user(user_id)
    if not u:
        raise HTTPException(404, "user not found")
    if daily_top_up(u):
        await store.put_user(u)
    return public_user(u)


@app.patch("/api/users/{user_id}")
async def patch_user(user_id: str, body: Prefs) -> dict:
    u = await game.update_prefs(user_id, body.model_dump())
    if not u:
        raise HTTPException(404, "user not found")
    return public_user(u)


@app.post("/api/users/{user_id}/activity")
async def activity(user_id: str, kind: str = Query(..., pattern="^(read_story|halftime)$"),
                   lang: str | None = Query(None, pattern="^(en|es|pt|fr)$")) -> dict:
    msgs = await game.record_activity(user_id, kind, lang)
    for m in msgs:
        await hub.to_user(user_id, m)
    u = await store.get_user(user_id)
    return {"ok": True, "events": msgs, "user": public_user(u) if u else None}


@app.get("/api/users/{user_id}/calls")
async def user_calls(user_id: str) -> list[dict]:
    return (await store.calls_for_user(user_id))[:50]


@app.post("/api/calls")
async def place_call(body: NewCall) -> dict:
    match_id = body.market_id.split(":")[0]
    room = rooms.get(match_id)
    if not room:
        raise HTTPException(404, "match not found")
    call, err, msgs = await game.place_call(body.user_id, room, body.market_id, body.option_id, body.stake,
                                            body.confidence)
    if err:
        raise HTTPException(400, err)
    for msg in msgs:
        await hub.to_user(body.user_id, msg)
    u = await store.get_user(body.user_id)
    return {"call": call, "user": public_user(u), "events": msgs}


@app.get("/api/stakes")
async def stakes() -> list[int]:
    return list(STAKES)


@app.get("/api/leaderboard")
async def leaderboard(code: str | None = None) -> dict:
    return await game.leaderboard(code)


@app.post("/api/leagues")
async def create_league(body: LeagueIn) -> dict:
    return await game.create_league(body.user_id, body.name or "My league")


@app.post("/api/leagues/join")
async def join_league(body: LeagueIn) -> dict:
    league = await game.join_league(body.user_id, body.code or "")
    if not league:
        raise HTTPException(404, "no league with that code")
    return league


@app.get("/api/model")
async def model_card() -> dict:
    """What the Gaffer is and how well it performs (from the offline evaluation)."""
    meta = data.model_meta
    eval_path = settings.data_dir / "evaluation.json"
    ev = {}
    if eval_path.exists():
        import json

        ev = json.loads(eval_path.read_text())
    return {"inplay": meta["inplay"], "strength_hyper": meta["strength_hyper"],
            "evaluation": {k: ev.get(k) for k in ("prematch", "calibration_error", "strength_recovery",
                                                  "log_bayes_factor_vs_naive")}}


@app.post("/api/admin/matches/{match_id}/restart")
async def restart(match_id: str, key: str, from_minute: float = 0.0, minute_seconds: float | None = None,
                  agents: bool = False):
    """Admin: replay a match now. agents=true has the agents write its stories even with no one watching
    (the evaluation checks them over plain HTTP); it lasts until that replay's full time."""
    if key != settings.admin_key:
        raise HTTPException(403, "bad key")
    if match_id not in data.matches:
        raise HTTPException(404, "match not found")
    if agents:
        _forced_agents.add(match_id)
    if match_id not in rooms:
        rooms[match_id] = MatchRoom(match_id, data)
    if settings.event_source == "eventhubs" and not _feed["fallback"]:
        _overrides.add(match_id)

        async def run_once() -> None:
            try:
                await replay(data, match_id, on_event, minute_seconds or settings.minute_seconds, from_minute)
            finally:
                _overrides.discard(match_id)

        _spawn(run_once())
    else:
        await scheduler.restart(match_id, from_minute, minute_seconds)
    return {"ok": True}


# ----------------------------------------------------------- web app (same origin)
_dist: Path = settings.web_dist
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    _fresh = {"Cache-Control": "no-cache"}  # always revalidate the shell so a deploy shows up right away

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        f = _dist / path
        if path and f.is_file() and f.resolve().is_relative_to(_dist.resolve()):
            return FileResponse(f, headers=_fresh if f.suffix in (".html", ".js", ".webmanifest") else None)
        return FileResponse(_dist / "index.html", headers=_fresh)
else:
    @app.get("/", include_in_schema=False)
    async def root():
        return JSONResponse({"service": "lasso-api", "docs": "/docs", "mcp": "/mcp"})
