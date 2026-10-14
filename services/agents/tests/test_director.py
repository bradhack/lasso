"""Runs the Match Director workflow end to end with a scripted chat client (no cloud needed)."""

import asyncio
import json
from collections.abc import Mapping, Sequence
from typing import Any

from agent_framework import Agent, BaseChatClient, ChatResponse, Message

from lasso_agents.director import build_director, parse_json
from lasso_agents.team import GAFFER, GAME_MASTER, NARRATOR, PERSONA, STATS, Team

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
                game_master=Agent(c, GAME_MASTER, name="game_master"), mcp=None)


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
