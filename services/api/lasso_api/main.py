"""Lasso API: live match rooms, the Gaffer's MCP server, the game, and realtime fan-out."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from lasso_engine.markets import generate_markets

from .agents_client import AgentsClient
from .config import settings
from .data import DemoData
from .feed import Scheduler, consume_forever
from .game import STAKES, GameService, daily_top_up, public_user
from .matchroom import MatchRoom
from .mcp_tools import build_mcp
from .realtime import LocalHub, make_hub
from .store import make_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("lasso.api")

data = DemoData(settings.data_dir)
rooms: dict[str, MatchRoom] = {mid: MatchRoom(mid, data) for mid in settings.featured_matches
                               if mid in data.matches}
hub = make_hub(settings.webpubsub_endpoint, settings.webpubsub_hub, settings.managed_identity_client_id)
store = make_store(settings.cosmos_endpoint, settings.cosmos_database, settings.managed_identity_client_id)
game = GameService(store)
agents = AgentsClient(settings.agents_url, settings.agents_timeout) if settings.agents_url else None
mcp = build_mcp(rooms)
scheduler = Scheduler(data, lambda mid, ev: on_event(mid, ev))
_last_stats: dict[str, float] = {}
_background: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    t = asyncio.create_task(coro)
    _background.add(t)
    t.add_done_callback(_background.discard)


# ------------------------------------------------------------------ pipeline
async def on_event(match_id: str, ev: dict) -> None:
    room = rooms.get(match_id)
    if room is None:
        room = rooms[match_id] = MatchRoom(match_id, data)
    if ev.get("type") == "match_reset":
        room.reset()
        await hub.to_group(f"match:{match_id}", {"type": "reset", "match": room.summary()})
        await hub.to_group("lobby", {"type": "status", "match": room.summary()})
        return
    for msg in room.ingest(ev):
        await publish(room, msg)
    now = time.time()
    if now - _last_stats.get(match_id, 0) > 4:
        _last_stats[match_id] = now
        await hub.to_group(f"match:{match_id}", {"type": "stats", "stats": room.stats_public()})


async def publish(room: MatchRoom, msg: dict) -> None:
    group = f"match:{room.match_id}"
    kind = msg["type"]
    await hub.to_group(group, msg)
    if kind in ("status", "meter"):
        if kind == "status" or int(time.time()) % 3 == 0:
            await hub.to_group("lobby", {"type": "status", "match": room.summary()})
    elif kind == "market_open":
        _spawn(game.bot_calls(room, room.markets[msg["market"]["market_id"]]))
    elif kind == "market_settled":
        _spawn(settle(room, msg["market"]["market_id"]))
    elif kind == "moment" and agents is not None:
        _spawn(enrich(room, msg["moment"]))


async def settle(room: MatchRoom, market_id: str) -> None:
    for user_id, msg in await game.settle(room, room.markets[market_id]):
        await hub.to_user(user_id, msg)


async def enrich(room: MatchRoom, moment: dict) -> None:
    """Ask the Match Director (five agents) for a richer package; merge it in when it arrives."""
    brief = {k: moment[k] for k in ("moment_id", "match_id", "trigger", "minute", "focus", "score",
                                    "before", "after")}
    brief["teams"] = list(room.names)
    brief["drivers"] = [{"component": d["component"], "delta_pts": d["delta"], "label": d["label"]["en"]}
                        for d in moment["drivers"]]
    t0 = time.time()
    pkg = await agents.produce(brief)
    if not pkg:
        return
    for key in ("headline", "story", "analyst", "club_lines"):
        if isinstance(pkg.get(key), dict) and pkg[key]:
            moment[key] = {**moment.get(key, {}), **{k: str(v) for k, v in pkg[key].items()}}
    moment["source"] = "agents"
    moment["agent_trace"] = pkg.get("trace", [])
    moment["latency_ms"] = int((time.time() - t0) * 1000)
    await hub.to_group(f"match:{room.match_id}", {"type": "moment_update", "moment": moment})
    challenge = pkg.get("challenge") or {}
    if challenge.get("market_id") and room.status == "live":
        cands = {c.market_id: c for c in generate_markets(room.gaffer, room.state, *room.names)}
        cand = cands.get(challenge["market_id"])
        open_kinds = {m.kind for m in room.markets.values() if m.status == "open"}
        if cand and cand.market_id.split("-")[0] not in open_kinds and len(open_kinds) < 2:
            for msg in room.open_market(cand, copy=str(challenge.get("copy", ""))[:140] or None):
                await publish(room, msg)


# ------------------------------------------------------------------- app
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    await game.bootstrap()
    async with mcp.session_manager.run():
        if settings.event_source == "eventhubs":
            _spawn(consume_forever(on_event))
        else:
            scheduler.start()
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


class LeagueIn(BaseModel):
    user_id: str
    name: str | None = None
    code: str | None = None


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "matches": len(rooms), "agents": bool(agents), "model": data.model_meta.get("version")}


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
async def activity(user_id: str, kind: str = Query(..., pattern="^read_story$")) -> dict:
    msgs = await game.record_activity(user_id, kind)
    for m in msgs:
        await hub.to_user(user_id, m)
    return {"ok": True, "events": msgs}


@app.get("/api/users/{user_id}/calls")
async def user_calls(user_id: str) -> list[dict]:
    return (await store.calls_for_user(user_id))[:50]


@app.post("/api/calls")
async def place_call(body: NewCall) -> dict:
    match_id = body.market_id.split(":")[0]
    room = rooms.get(match_id)
    if not room:
        raise HTTPException(404, "match not found")
    call, err = await game.place_call(body.user_id, room, body.market_id, body.option_id, body.stake,
                                      body.confidence)
    if err:
        raise HTTPException(400, err)
    u = await store.get_user(body.user_id)
    return {"call": call, "user": public_user(u)}


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
async def restart(match_id: str, key: str, from_minute: float = 0.0, minute_seconds: float | None = None):
    if key != settings.admin_key:
        raise HTTPException(403, "bad key")
    if match_id not in data.matches:
        raise HTTPException(404, "match not found")
    if match_id not in rooms:
        rooms[match_id] = MatchRoom(match_id, data)
    await scheduler.restart(match_id, from_minute, minute_seconds)
    return {"ok": True}


# ----------------------------------------------------------- web app (same origin)
_dist: Path = settings.web_dist
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        f = _dist / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(_dist / "index.html")
else:
    @app.get("/", include_in_schema=False)
    async def root():
        return JSONResponse({"service": "lasso-api", "docs": "/docs", "mcp": "/mcp"})
