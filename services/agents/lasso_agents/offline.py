"""Offline chat client: lets the whole A2A + workflow chain run without a model deployment.

It returns minimal, honest JSON derived from the brief (no invented prose), so
the API keeps its own template narration. Used for local plumbing tests only;
production uses Microsoft Foundry.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from agent_framework import BaseChatClient, ChatResponse, Message


class OfflineChatClient(BaseChatClient):
    def _inner_get_response(self, *, messages: Sequence[Message], stream: bool, options: Mapping[str, Any],
                            **kwargs: Any):
        async def respond() -> ChatResponse:
            text = " ".join(m.text or "" for m in messages)
            start = text.find("Brief: ")
            brief: dict = {}
            if start >= 0:
                raw = text[start + 7:].split("\n", 1)[0]
                try:
                    brief = json.loads(raw)
                except json.JSONDecodeError:
                    brief = {}
            out: dict = {}
            instructions = str(options.get("instructions") or "") + text
            if "Gaffer's voice" in instructions and brief.get("drivers"):
                d = brief["drivers"][0]
                out = {"summary": f"Biggest driver: {d['label']} ({d.get('points', d.get('delta_pts', 0)):+} pts).",
                       "confidence_note": "offline mode"}
            elif "Stats agent" in instructions:
                out = {"facts": [], "momentum": "even", "spotlight": ""}
            return ChatResponse(messages=[Message("assistant", [json.dumps(out)])])
        return respond()
