"""Lasso's insights stream to Microsoft Fabric (Real-Time Intelligence).

When LASSO_FABRIC_CONNECTION holds an Eventstream custom endpoint's connection string, every agent-written story,
every Ask the Gaffer answer and every agent run inside them is sent there as one flat JSON event. Fabric stores
them in an Eventhouse (KQL database) and the Lasso dashboard charts them: agent latency and tokens, what the code
checks caught, how the agents recovered, and how the matches moved. See docs/FABRIC.md and fabric/.

Sending never blocks a match or a fan: events go on a bounded queue and a background task sends them in batches;
if Fabric is unreachable, events are dropped and the app carries on.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone

log = logging.getLogger("lasso.insights")

QUEUE_MAX = 5000
FLUSH_SECONDS = 2.0
_queue: asyncio.Queue | None = None
_enabled = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _put(event: dict) -> None:
    if not _enabled or _queue is None:
        return
    try:
        _queue.put_nowait({"ts": _now(), **event})
    except asyncio.QueueFull:
        pass  # Fabric is behind or down: drop, never slow the app


def _runs(trace: list[dict]) -> list[dict]:
    return [t for t in trace or [] if t.get("agent") != "checks"]


def _summary(trace: list[dict]) -> dict:
    """What a story's or an answer's agent trace adds up to."""
    runs = _runs(trace)
    checks = next((t for t in trace or [] if t.get("agent") == "checks"), {})
    fixes = list(checks.get("fixes") or [])
    return {
        "agents": len({t.get("agent") for t in runs}),
        "runs": len(runs),
        "tokens": sum((t.get("in") or 0) + (t.get("out") or 0) for t in runs),
        "tool_calls": sum(len(t.get("tools") or []) for t in runs),
        "tools": ",".join(tl.get("name", "") for t in runs for tl in t.get("tools") or []),
        "checks": checks.get("checks") or 0,
        "fixes": ",".join(fixes),
        "fix_count": len([f for f in fixes if f not in ("wording", "length")]),
        "timeouts": sum(1 for t in runs if t.get("error") == "TimeoutError"),
        "recoveries": sum(1 for t in runs if t.get("hedge") or t.get("retry") or t.get("recovered")
                          or t.get("error") == "Superseded"),
    }


def _agent_runs(trace: list[dict], parent_kind: str, parent_id: str, match_id: str) -> None:
    for t in _runs(trace):
        _put({"kind": "agent_run", "parent_kind": parent_kind, "parent_id": parent_id, "match_id": match_id,
              "agent": t.get("agent"), "ms": t.get("ms") or 0, "ok": bool(t.get("ok")), "error": t.get("error") or "",
              "stage": t.get("stage") or 0, "model": t.get("model") or "",
              "tokens_in": t.get("in") or 0, "tokens_out": t.get("out") or 0, "reasoning": t.get("reasoning") or 0,
              "tool_calls": len(t.get("tools") or []),
              "tools": ",".join(tl.get("name", "") for tl in t.get("tools") or []),
              "hedge": bool(t.get("hedge")), "retry": bool(t.get("retry")), "recovered": bool(t.get("recovered"))})


def story(room, moment: dict) -> None:
    """An agent-written (or agent-checked) story, after the code checks."""
    if not _enabled:
        return
    trace = moment.get("agent_trace") or []
    after = moment.get("after") or {}
    before = moment.get("before") or {}
    _put({"kind": "story", "match_id": room.match_id, "home": room.names[0], "away": room.names[1],
          "moment_id": moment.get("moment_id"), "trigger": moment.get("trigger"), "minute": moment.get("minute"),
          "score": "-".join(str(g) for g in moment.get("score") or []), "source": moment.get("source") or "template",
          "latency_ms": moment.get("latency_ms") or 0, "headline": (moment.get("headline") or {}).get("en", ""),
          "p_home": round(100 * float(after.get("home", 0)), 1), "p_draw": round(100 * float(after.get("draw", 0)), 1),
          "p_away": round(100 * float(after.get("away", 0)), 1),
          "swing": round(100 * max(abs(float(after.get(k, 0)) - float(before.get(k, 0))) for k in ("home", "draw", "away")), 1)
          if after and before else 0.0,
          **_summary(trace)})
    _agent_runs(trace, "story", moment.get("moment_id") or "", room.match_id)


def answer(room, *, ask_id: str, lang: str, persona: str, mode: str, source: str, latency_ms: int,
           trace: list[dict], minute: int) -> None:
    """An Ask the Gaffer answer, after the code checks (never the question or answer text: fans' words stay in
    the app)."""
    if not _enabled:
        return
    _put({"kind": "answer", "match_id": room.match_id, "home": room.names[0], "away": room.names[1],
          "ask_id": ask_id, "minute": minute, "lang": lang, "persona": persona, "mode": mode, "source": source,
          "latency_ms": latency_ms, "score": "-".join(str(g) for g in room.state.goals), **_summary(trace)})
    _agent_runs(trace, "answer", ask_id, room.match_id)


async def run(connection: str) -> None:
    """Send queued events to the Eventstream in batches, for as long as the app runs."""
    global _queue, _enabled
    from azure.eventhub import EventData
    from azure.eventhub.aio import EventHubProducerClient

    _queue = asyncio.Queue(maxsize=QUEUE_MAX)
    _enabled = True
    producer = EventHubProducerClient.from_connection_string(connection)
    log.info("insights: sending stories, answers and agent runs to Microsoft Fabric")
    async with producer:
        while True:
            first = await _queue.get()
            events = [first]
            deadline = time.monotonic() + FLUSH_SECONDS
            while len(events) < 500 and (left := deadline - time.monotonic()) > 0:
                try:
                    events.append(await asyncio.wait_for(_queue.get(), timeout=left))
                except asyncio.TimeoutError:
                    break
            try:
                batch = await producer.create_batch()
                for e in events:
                    data = EventData(json.dumps(e, ensure_ascii=False))
                    try:
                        batch.add(data)
                    except ValueError:  # batch full: send it and start another
                        await producer.send_batch(batch)
                        batch = await producer.create_batch()
                        batch.add(data)
                await producer.send_batch(batch)
            except Exception as e:  # noqa: BLE001
                log.warning("insights: couldn't send %d events to Fabric: %r", len(events), e)
