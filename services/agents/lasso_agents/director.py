"""The Match Director: a fan-out / fan-in workflow over the five agents.

    brief ─┬─> Stats ───┐            ┌─> Narrator ────┐
           │            ├─> context ─┼─> Persona ─────┼─> package
           └─> Gaffer ──┘            └─> Game Master ─┘

Stage one gathers facts and the model's explanation in parallel; stage two
writes, personalizes and creates a challenge in parallel. Every agent call is
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
WRITER_TIME = 1.6  # the Narrator and Persona write four languages each, so they get longer than the lookups


def parse_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}


def tool_calls(resp) -> list[dict]:
    """The tools an agent called (MCP tools arrive as function calls), with their arguments, for the trace."""
    calls = []
    for m in getattr(resp, "messages", None) or []:
        for c in getattr(m, "contents", None) or []:
            if getattr(c, "type", "") in ("function_call", "mcp_server_tool_call") and getattr(c, "name", None):
                args = c.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                args = {k: v for k, v in (args or {}).items() if k != "match_id"}  # same for every call
                calls.append({"name": c.name, "args": args} if args else {"name": c.name})
    return calls


async def run_agent(agent, prompt: str, timeout: float, stage: int = 1, model: str | None = None
                    ) -> tuple[dict, dict]:
    started = time.time()
    t0 = time.perf_counter()
    usage: dict = {}
    tools: list[dict] = []
    try:
        resp = await asyncio.wait_for(agent.run(prompt), timeout=timeout)
        out = parse_json(resp.text)
        ok = bool(out)
        if not ok:
            log.warning("%s returned no JSON: %r", agent.name, (resp.text or "")[:300])
        u = getattr(resp, "usage_details", None) or {}
        usage = {"in": u.get("input_token_count"), "out": u.get("output_token_count"),
                 "reasoning": u.get("reasoning_output_token_count"), "turns": len(getattr(resp, "messages", []) or [])}
        tools = tool_calls(resp)
    except Exception as e:  # noqa: BLE001
        log.warning("%s failed: %r", agent.name, e)
        out, ok = {}, False
        usage = {"error": type(e).__name__}
    ms = int((time.perf_counter() - t0) * 1000)
    log.info("agent %s ok=%s %dms %s tools=%s", agent.name, ok, ms, usage, [t["name"] for t in tools])
    trace = {"agent": agent.name, "ms": ms, "ok": ok, "stage": stage, "start": round(started, 3), "tools": tools,
             **{k: v for k, v in usage.items() if v is not None}}
    if model:
        trace["model"] = model
    return out, trace


def build_director(team: Team, timeout: float = 25.0) -> Workflow:
    @executor(id="brief")
    async def brief(messages: list[Message], ctx: WorkflowContext[dict]) -> None:
        text = messages[-1].text if messages else "{}"
        await ctx.send_message({"brief": parse_json(text)})

    @executor(id="stats_step")
    async def stats_step(msg: dict, ctx: WorkflowContext[dict]) -> None:
        b = msg["brief"]
        out, tr = await run_agent(team.stats, f"Brief: {json.dumps(b)}\nMatch id: {b.get('match_id')}", timeout,
                                  1, team.model_of("stats"))
        await ctx.send_message({"brief": b, "stats": out, "trace": [tr]})

    @executor(id="gaffer_step")
    async def gaffer_step(msg: dict, ctx: WorkflowContext[dict]) -> None:
        b = msg["brief"]
        out, tr = await run_agent(team.gaffer, f"Brief: {json.dumps(b)}\nMatch id: {b.get('match_id')}", timeout,
                                  1, team.model_of("gaffer"))
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
        out, tr = await run_agent(team.narrator, _writer_prompt(c), timeout * WRITER_TIME, 2, team.model_of("narrator"))
        await ctx.send_message({"narrator": out, "trace": [tr], "base": c})

    @executor(id="persona_step")
    async def persona_step(c: dict, ctx: WorkflowContext[dict]) -> None:
        out, tr = await run_agent(team.persona, _writer_prompt(c), timeout * WRITER_TIME, 2, team.model_of("persona"))
        await ctx.send_message({"persona": out, "trace": [tr], "base": c})

    @executor(id="game_master_step")
    async def game_master_step(c: dict, ctx: WorkflowContext[dict]) -> None:
        b = c["brief"]
        out, tr = await run_agent(team.game_master, f"Brief: {json.dumps(b)}\nMatch id: {b.get('match_id')}",
                                  timeout, 2, team.model_of("game_master"))
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


def build_press_room(team: Team, timeout: float = 25.0) -> Workflow:
    """Ask the Gaffer: a fan's question goes to the Scout, who picks the MCP tools that answer it; the
    Gaffer (the presser) then answers in the fan's language from the Scout's facts alone.

        question ─> Scout (MCP tools) ─> Presser (no tools) ─> answer

    The Presser has no tools, so a question can't steer it into calling anything; the Scout's tools are
    read-only. Both are time-boxed and traced like the Director's agents.
    """

    @executor(id="question")
    async def question(messages: list[Message], ctx: WorkflowContext[dict]) -> None:
        text = messages[-1].text if messages else "{}"
        await ctx.send_message({"brief": parse_json(text)})

    @executor(id="scout_step")
    async def scout_step(msg: dict, ctx: WorkflowContext[dict]) -> None:
        b = msg["brief"]
        out, tr = await run_agent(team.scout, f"Brief: {json.dumps(b)}\nMatch id: {b.get('match_id')}", timeout,
                                  1, team.model_of("scout"))
        await ctx.send_message({"brief": b, "scout": out, "trace": [tr]})

    @executor(id="presser_step")
    async def presser_step(c: dict, ctx: WorkflowContext[None, str]) -> None:
        b = c["brief"]
        if c.get("scout", {}).get("on_topic") is False:
            # The Scout judged the question off topic: don't let the writer be tempted to answer it.
            pkg = {"ask_id": b.get("ask_id"), "answer": "", "off_topic": True, "followups": [], "facts": [],
                   "trace": c["trace"]}
            await ctx.yield_output(json.dumps(pkg, ensure_ascii=False))
            return
        out, tr = await run_agent(team.presser, f"Brief: {json.dumps(b)}\nNotes: {json.dumps(c.get('scout', {}))}",
                                  timeout, 2, team.model_of("presser"))
        pkg = {"ask_id": b.get("ask_id"), "answer": out.get("answer", ""), "followups": out.get("followups", []),
               "facts": c.get("scout", {}).get("facts", []), "trace": c["trace"] + [tr]}
        await ctx.yield_output(json.dumps(pkg, ensure_ascii=False))

    return (
        WorkflowBuilder(name="press-room", description="Answers a fan's question about a live match",
                        start_executor=question)
        .add_edge(question, scout_step)
        .add_edge(scout_step, presser_step)
        .build()
    )
