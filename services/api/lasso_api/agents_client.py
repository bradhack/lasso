"""Calls the Match Director (the agents' workflow) over the A2A protocol."""

from __future__ import annotations

import asyncio
import json
import logging

log = logging.getLogger("lasso.agents")


class AgentsClient:
    def __init__(self, url: str, timeout: float, key: str = ""):
        self.url = url.rstrip("/") + "/"
        self.timeout = timeout
        self.key = key  # the agents service only runs for requests that carry it
        self._agent = None

    def _get(self):
        if self._agent is None:
            from agent_framework.a2a import A2AAgent

            import httpx

            http = httpx.AsyncClient(timeout=self.timeout, headers={"X-Lasso-Key": self.key} if self.key else None)
            self._agent = A2AAgent(name="match-director", url=self.url, timeout=self.timeout, http_client=http)
        return self._agent

    async def produce(self, request: dict) -> dict | None:
        """Send a moment brief; return the enriched moment package, or None on failure."""
        try:
            resp = await asyncio.wait_for(self._get().run(json.dumps(request)), timeout=self.timeout)
            text = resp.text.strip()
            start, end = text.find("{"), text.rfind("}")
            return json.loads(text[start:end + 1]) if start >= 0 else None
        except Exception as e:  # noqa: BLE001
            log.warning("agents unavailable (%s); keeping template narration", e)
            return None
