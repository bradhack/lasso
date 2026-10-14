"""The Match Director: a fan-out / fan-in workflow over the five agents.

    brief ─┬─> Stats ───┐            ┌─> Narrator ────┐
           │            ├─> context ─┼─> Persona ─────┼─> package
           └─> Gaffer ──┘            └─> Game Master ─┘

Stage one gathers facts and the model's explanation in parallel; stage two
writes, personalises and creates a challenge in parallel. Every agent call is
time-boxed and traced; a failed agent simply contributes nothing, and the API
keeps its instant template text for that part.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from agent_framework import Message, Workflow, WorkflowBuilder, WorkflowContext, executor

from .team import Team

log = logging.getLogger("lasso.director")


def parse_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}


async def run_agent(agent, prompt: str, timeout: float) -> tuple[dict, dict]:
    t0 = time.perf_counter()
    try:
        resp = await asyncio.wait_for(agent.run(prompt), timeout=timeout)
        out = parse_json(resp.text)
        ok = bool(out)
    except Exception as e:  # noqa: BLE001
        log.warning("%s failed: %s", agent.name, e)
        out, ok = {}, False
    return out, {"agent": agent.name, "ms": int((time.perf_counter() - t0) * 1000), "ok": ok}


def build_director(team: Team, timeout: float = 25.0) -> Workflow:
    @executor(id="brief")
    async def brief(messages: list[Message], ctx: WorkflowContext[dict]) -> None:
        text = messages[-1].text if messages else "{}"
        await ctx.send_message({"brief": parse_json(text)})

    @executor(id="stats_step")
    async def stats_step(msg: dict, ctx: WorkflowContext[dict]) -> None:
        b = msg["brief"]
        out, tr = await run_agent(team.stats, f"Brief: {json.dumps(b)}\nMatch id: {b.get('match_id')}", timeout)
        await ctx.send_message({"brief": b, "stats": out, "trace": [tr]})

    @executor(id="gaffer_step")
    async def gaffer_step(msg: dict, ctx: WorkflowContext[dict]) -> None:
        b = msg["brief"]
        out, tr = await run_agent(team.gaffer, f"Brief: {json.dumps(b)}\nMatch id: {b.get('match_id')}", timeout)
        await ctx.send_message({"brief": b, "gaffer": out, "trace": [tr]})

    @executor(id="context")
    async def context(parts: list[dict], ctx: WorkflowContext[dict]) -> None:
        merged: dict[str, Any] = {"trace": []}
        for p in parts:
            merged["trace"] += p.pop("trace", [])
            merged.update(p)
        await ctx.send_message(merged)

    def _writer_prompt(c: dict) -> str:
        return (f"Brief: {json.dumps(c['brief'])}\nStats agent: {json.dumps(c.get('stats', {}))}\n"
                f"Gaffer: {json.dumps(c.get('gaffer', {}))}")

    @executor(id="narrator_step")
    async def narrator_step(c: dict, ctx: WorkflowContext[dict]) -> None:
        out, tr = await run_agent(team.narrator, _writer_prompt(c), timeout)
        await ctx.send_message({"narrator": out, "trace": [tr], "base": c})

    @executor(id="persona_step")
    async def persona_step(c: dict, ctx: WorkflowContext[dict]) -> None:
        out, tr = await run_agent(team.persona, _writer_prompt(c), timeout)
        await ctx.send_message({"persona": out, "trace": [tr], "base": c})

    @executor(id="game_master_step")
    async def game_master_step(c: dict, ctx: WorkflowContext[dict]) -> None:
        b = c["brief"]
        out, tr = await run_agent(team.game_master, f"Brief: {json.dumps(b)}\nMatch id: {b.get('match_id')}",
                                  timeout)
        await ctx.send_message({"game_master": out, "trace": [tr], "base": c})

    @executor(id="package")
    async def package(parts: list[dict], ctx: WorkflowContext[None, str]) -> None:
        base = parts[0]["base"]
        trace = list(base.get("trace", []))
        pkg: dict[str, Any] = {"moment_id": base["brief"].get("moment_id"), "facts": base.get("stats", {}),
                               "gaffer": base.get("gaffer", {})}
        for p in parts:
            trace += p.get("trace", [])
            if "narrator" in p:
                pkg["headline"] = p["narrator"].get("headline", {})
                pkg["story"] = p["narrator"].get("story", {})
            if "persona" in p:
                pkg["analyst"] = p["persona"].get("analyst", {})
                pkg["club_lines"] = p["persona"].get("club_lines", {})
            if "game_master" in p and p["game_master"].get("market_id"):
                pkg["challenge"] = p["game_master"]
        pkg["trace"] = trace
        await ctx.yield_output(json.dumps(pkg, ensure_ascii=False))

    return (
        WorkflowBuilder(name="match-director", description="Turns a live moment into a story, a personal "
                        "angle and a challenge", start_executor=brief)
        .add_fan_out_edges(brief, [stats_step, gaffer_step])
        .add_fan_in_edges([stats_step, gaffer_step], context)
        .add_fan_out_edges(context, [narrator_step, persona_step, game_master_step])
        .add_fan_in_edges([narrator_step, persona_step, game_master_step], package)
        .build()
    )
