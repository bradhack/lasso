"""Runs the Match Director workflow end to end with a scripted chat client (no cloud needed)."""

import asyncio
import json
from collections.abc import Mapping, Sequence
from typing import Any

from agent_framework import Agent, BaseChatClient, ChatResponse, Message

from lasso_agents.director import build_director, build_press_room, parse_json
from lasso_agents.team import GAFFER, GAME_MASTER, NARRATOR, PERSONA, PRESSER, SCOUT, STATS, Team

SCRIPT = {
    "Stats agent for Lasso": {"facts": ["xG 1.4-0.6", "possession 58%", "fastest shot 112 km/h"],
                              "momentum": "home", "spotlight": "Adam Penke, 0.9 xG"},
    "Gaffer's voice": {"summary": "The red card cost Eastholme 21 points.", "confidence_note": "Still open."},
    "You are the Narrator": {"headline": {"en": "Ten men, one winner", "es": "Diez y ganan", "pt": "Dez e vencem",
                                          "fr": "À dix, ils gagnent"},
                             "story": {"en": "From 15% to 83%.", "es": "Del 15% al 83%.", "pt": "De 15% para 83%.",
                                       "fr": "De 15 % à 83 %."}},
    "Persona agent": {"analyst": {"en": "xG 1.4 v 0.6."}, "club_lines": {"home": {"en": "Believe!"},
                                                                         "away": {"en": "Chin up."}}},
    "Scout for Lasso": {"facts": ["Red card for Lorford at 5'", "Chances fell from 41% to 19%"], "on_topic": True},
    "press conference": {"answer": "The red card at 5' cost us 22 points.", "followups": ["Can we still win?",
                                                                                         "Who's playing best?"]},
    "Game Master": {"market_id": "comeback-2-82", "copy": "Fancy a comeback? Stake your biscuits."},
}


class ScriptedClient(BaseChatClient):
    def _inner_get_response(self, *, messages: Sequence[Message], stream: bool, options: Mapping[str, Any],
                            **kwargs: Any):
        async def respond() -> ChatResponse:
            system = " ".join(m.text or "" for m in messages)
            instructions = options.get("instructions") or ""
            text = system + " " + str(instructions)
            for key, payload in SCRIPT.items():
                if key in text:
                    return ChatResponse(messages=[Message("assistant", [json.dumps(payload)])])
            return ChatResponse(messages=[Message("assistant", ["{}"])])
        return respond()


def make_team() -> Team:
    c = ScriptedClient()
    return Team(stats=Agent(c, STATS, name="stats"), gaffer=Agent(c, GAFFER, name="gaffer"),
                narrator=Agent(c, NARRATOR, name="narrator"), persona=Agent(c, PERSONA, name="persona"),
                game_master=Agent(c, GAME_MASTER, name="game_master"), mcp=None,
                scout=Agent(c, SCOUT, name="scout"), presser=Agent(c, PRESSER, name="presser"))


def test_parse_json_tolerates_prose():
    assert parse_json('Sure! {"a": 1} done') == {"a": 1}
    assert parse_json("no json here") == {}


def test_director_produces_full_package():
    agent = build_director(make_team()).as_agent(name="Match Director")
    brief = {"moment_id": "m1", "match_id": "S5-MD07-03", "trigger": "goal", "minute": 82,
             "teams": ["Eastholme Rangers", "Brackenford City"], "before": {"home": 0.15}, "after": {"home": 0.83}}
    resp = asyncio.run(agent.run(json.dumps(brief)))
    pkg = parse_json(resp.text)
    assert pkg["moment_id"] == "m1"
    assert pkg["headline"]["fr"] == "À dix, ils gagnent"
    assert pkg["club_lines"]["home"]["en"] == "Believe!"
    assert pkg["challenge"]["market_id"] == "comeback-2-82"
    assert {t["agent"] for t in pkg["trace"]} == {"stats", "gaffer", "narrator", "persona", "game_master"}
    assert all(t["ok"] for t in pkg["trace"])


def test_press_room_answers_a_question():
    agent = build_press_room(make_team()).as_agent(name="Press Room")
    brief = {"kind": "ask", "ask_id": "q1", "match_id": "S5-MD07-03", "lang": "en",
             "question": "Why did our chances drop early?"}
    pkg = parse_json(asyncio.run(agent.run(json.dumps(brief))).text)
    assert pkg["ask_id"] == "q1"
    assert pkg["answer"].startswith("The red card")
    assert len(pkg["followups"]) == 2
    assert [t["agent"] for t in pkg["trace"]] == ["scout", "presser"]
    assert all(t["ok"] for t in pkg["trace"])


def test_tool_calls_are_traced_without_the_match_id():
    from types import SimpleNamespace as NS

    from lasso_agents.director import tool_calls

    resp = NS(messages=[NS(contents=[NS(type="function_call", name="chances_at",
                                        arguments='{"match_id": "S5-MD07-03", "minute": 45}'),
                                     NS(type="function_call", name="match_story", arguments={"match_id": "x"}),
                                     NS(type="text", name=None, arguments=None)])])
    assert tool_calls(resp) == [{"name": "chances_at", "args": {"minute": 45}}, {"name": "match_story"}]


def test_press_room_skips_the_writer_when_the_scout_rules_a_question_off_topic():
    SCRIPT["Scout for Lasso"] = {"facts": [], "on_topic": False}
    try:
        agent = build_press_room(make_team()).as_agent(name="Press Room")
        pkg = parse_json(asyncio.run(agent.run(json.dumps({"kind": "ask", "ask_id": "q2",
                                                             "question": "What's the capital of France?"}))).text)
    finally:
        SCRIPT["Scout for Lasso"] = {"facts": ["Red card for Lorford at 5'", "Chances fell from 41% to 19%"],
                                     "on_topic": True}
    assert pkg["off_topic"] is True and pkg["answer"] == ""
    assert [t["agent"] for t in pkg["trace"]] == ["scout"]
