"""Realtime fan-out: Azure Web PubSub in the cloud, a protocol-compatible websocket hub locally.

Both speak the ``json.webpubsub.azure.v1`` subprotocol, so the web app uses
exactly the same client code against either.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict

from fastapi import WebSocket, WebSocketDisconnect

log = logging.getLogger("lasso.realtime")


class LocalHub:
    def __init__(self) -> None:
        self.groups: dict[str, set[WebSocket]] = defaultdict(set)
        self.users: dict[str, set[WebSocket]] = defaultdict(set)

    async def negotiate(self, user_id: str, base_ws_url: str) -> dict:
        return {"url": f"{base_ws_url}/ws?user_id={user_id}"}

    async def serve(self, ws: WebSocket, user_id: str) -> None:
        await ws.accept(subprotocol="json.webpubsub.azure.v1")
        self.users[user_id].add(ws)
        await ws.send_text(json.dumps({"type": "system", "event": "connected", "userId": user_id}))
        try:
            while True:
                msg = json.loads(await ws.receive_text())
                if msg.get("type") in ("joinGroup", "leaveGroup"):
                    g = msg.get("group", "")
                    if msg["type"] == "joinGroup":
                        self.groups[g].add(ws)
                    else:
                        self.groups[g].discard(ws)
                    if "ackId" in msg:
                        await ws.send_text(json.dumps({"type": "ack", "ackId": msg["ackId"], "success": True}))
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            self.users[user_id].discard(ws)
            for members in self.groups.values():
                members.discard(ws)

    async def _send(self, sockets: set[WebSocket], envelope: dict) -> None:
        text = json.dumps(envelope, default=float)
        dead = []
        for ws in list(sockets):
            try:
                await ws.send_text(text)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            sockets.discard(ws)

    async def has_viewers(self, group: str) -> bool:
        return bool(self.groups.get(group))

    async def to_group(self, group: str, data: dict) -> None:
        await self._send(self.groups.get(group, set()),
                         {"type": "message", "from": "group", "group": group, "dataType": "json", "data": data})

    async def to_user(self, user_id: str, data: dict) -> None:
        await self._send(self.users.get(user_id, set()),
                         {"type": "message", "from": "server", "dataType": "json", "data": data})


class WebPubSubHub:
    def __init__(self, endpoint: str, hub: str, client_id: str = "") -> None:
        from azure.identity.aio import DefaultAzureCredential
        from azure.messaging.webpubsubservice.aio import WebPubSubServiceClient

        self._cred = DefaultAzureCredential(managed_identity_client_id=client_id or None)
        # A realtime push must never hold up a match: retry once, briefly, and never wait out a long
        # "try again later" (which is what a used-up message allowance returns).
        self.client = WebPubSubServiceClient(endpoint=endpoint, hub=hub, credential=self._cred,
                                             retry_total=1, retry_backoff_factor=0.3, retry_backoff_max=1,
                                             retry_mode="fixed")
        self._sem = asyncio.Semaphore(32)
        self._viewers: dict[str, tuple[float, bool]] = {}
        self._failures = 0

    async def has_viewers(self, group: str) -> bool:
        now = asyncio.get_event_loop().time()
        hit = self._viewers.get(group)
        # Remember "watched" for 15s, but re-check an empty group after 5s so a new viewer starts getting
        # live updates quickly (they load the full snapshot when they open the match anyway).
        if hit and now - hit[0] < (15 if hit[1] else 5):
            return hit[1]
        try:
            exists = bool(await self.client.group_exists(group))
        except Exception:  # noqa: BLE001
            exists = True
        self._viewers[group] = (now, exists)
        return exists

    async def negotiate(self, user_id: str, base_ws_url: str) -> dict:
        token = await self.client.get_client_access_token(
            user_id=user_id, roles=["webpubsub.joinLeaveGroup"], minutes_to_expire=180)
        return {"url": token["url"]}

    async def to_group(self, group: str, data: dict) -> None:
        # Nobody in the group: skip the send. This saves most of the message allowance when no one is watching.
        if not await self.has_viewers(group):
            return
        await self._send(self.client.send_to_group(group, message=json.dumps(data, default=float),
                                                   content_type="application/json"))

    async def to_user(self, user_id: str, data: dict) -> None:
        await self._send(self.client.send_to_user(user_id, message=json.dumps(data, default=float),
                                                  content_type="application/json"))

    async def _send(self, call) -> None:
        async with self._sem:
            try:
                await asyncio.wait_for(call, timeout=SEND_TIMEOUT)
                self._failures = 0
            except Exception as e:  # noqa: BLE001
                self._failures += 1
                if self._failures == 1 or self._failures % 200 == 0:  # don't flood the logs during an outage
                    log.warning("web pubsub send failed (%d in a row): %r", self._failures, e)


SEND_TIMEOUT = 3.0  # seconds; a slow or refused push is dropped rather than delaying the match


def make_hub(endpoint: str, hub: str, client_id: str = ""):
    if endpoint:
        log.info("using Azure Web PubSub %s / %s", endpoint, hub)
        return WebPubSubHub(endpoint, hub, client_id)
    return LocalHub()
