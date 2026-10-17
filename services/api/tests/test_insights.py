"""The insights stream to Microsoft Fabric: flat events, no fans' words, never blocking."""

import asyncio
from types import SimpleNamespace as NS

from lasso_api import insights

TRACE = [
    {"agent": "scout", "ms": 25001, "ok": False, "error": "TimeoutError", "tools": []},
    {"agent": "presser", "ms": 10000, "ok": False, "error": "Superseded"},
    {"agent": "presser", "ms": 1900, "ok": True, "in": 3000, "out": 120, "hedge": True,
     "tools": [{"name": "gaffers_gauge"}]},
    {"agent": "checks", "ok": True, "checks": 19, "fixes": ["wording", "wrong_leader"]},
]
ROOM = NS(match_id="S5-MD07-03", names=["Eastholme Rangers", "Brackenford City"], state=NS(goals=[2, 1]))


def _capture():
    insights._queue = asyncio.Queue(maxsize=100)
    insights._enabled = True
    return insights._queue


def _drain(q):
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


def test_summary_counts_agents_tokens_fixes_and_recoveries():
    s = insights._summary(TRACE)
    assert s["agents"] == 2 and s["runs"] == 3 and s["tokens"] == 3120 and s["tool_calls"] == 1
    assert s["fixes"] == "wording,wrong_leader" and s["fix_count"] == 1  # tidying doesn't count as a fix
    assert s["timeouts"] == 1 and s["recoveries"] == 2


def test_answer_sends_a_summary_and_one_event_per_agent_run_without_the_fans_words():
    q = _capture()
    insights.answer(ROOM, ask_id="a1", lang="fr", persona="fan", mode="team", source="agents", latency_ms=27000,
                    trace=TRACE, minute=89)
    events = _drain(q)
    assert [e["kind"] for e in events] == ["answer", "agent_run", "agent_run", "agent_run"]
    assert events[0]["score"] == "2-1" and events[0]["fix_count"] == 1
    assert all("question" not in e and "answer" not in e for e in events)
    assert events[3]["agent"] == "presser" and events[3]["hedge"] is True


def test_story_event_has_the_chances_and_the_swing():
    q = _capture()
    moment = {"moment_id": "m9", "trigger": "goal", "minute": 82, "score": [2, 1], "source": "agents",
              "latency_ms": 12000, "headline": {"en": "Penke's late strike"},
              "before": {"home": 0.16, "draw": 0.6, "away": 0.24}, "after": {"home": 0.83, "draw": 0.14, "away": 0.03},
              "agent_trace": TRACE}
    insights.story(ROOM, moment)
    ev = _drain(q)[0]
    assert ev["kind"] == "story" and ev["p_home"] == 83.0 and ev["swing"] == 67.0


def test_nothing_is_sent_when_fabric_is_not_configured():
    insights._enabled = False
    insights.answer(ROOM, ask_id="a2", lang="en", persona="fan", mode="team", source="agents", latency_ms=1,
                    trace=TRACE, minute=1)  # no queue, no error


def test_a_full_queue_drops_instead_of_blocking():
    insights._queue = asyncio.Queue(maxsize=1)
    insights._enabled = True
    for _ in range(3):
        insights._put({"kind": "x"})
    assert insights._queue.qsize() == 1
    insights._enabled = False
