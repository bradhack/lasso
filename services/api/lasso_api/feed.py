"""Match Feed: replays synthetic matches in (accelerated) real time.

Local mode calls the match room directly. In Azure, the same scheduler runs
as its own container app and publishes to Event Hubs; the API consumes them.

    python -m lasso_api.feed            # publish to Event Hubs (needs EVENTHUB_* settings)
"""

from __future__ import annotations

import asyncio
import json
import logging
import zlib
from collections.abc import Awaitable, Callable

from .config import Settings, settings
from .data import DemoData

log = logging.getLogger("lasso.feed")
OnEvent = Callable[[str, dict], Awaitable[None]]
HALF_TIME_BREAK_SECONDS = 12

# VAR: some goals are checked (and stand), and at most one big chance per match is shown as a goal and then ruled
# out. Synthetic like everything else, chosen deterministically so every replay of a match is the same.
VAR_REASONS = ("offside", "handball", "foul")
VAR_MIN_SECONDS = 8.0
SHOWCASE_VAR = {"S5-MD07-03": {93: ("ruled_out", "offside"), 1021: ("stands", "offside")}}


def var_plan(match_id: str, events: list[dict]) -> dict[int, tuple[str, str]]:
    """seq -> (decision, reason) for the shots that get a VAR check in this match."""
    if match_id in SHOWCASE_VAR:
        return dict(SHOWCASE_VAR[match_id])
    plan: dict[int, tuple[str, str]] = {}
    ruled_out = False
    for e in events:
        if e["type"] != "shot":
            continue
        h = zlib.crc32(f"{match_id}:{e['seq']}".encode())
        reason = VAR_REASONS[h % len(VAR_REASONS)]
        xg = float(e.get("xg") or 0)
        if e.get("outcome") and h % 100 < 30:
            plan[e["seq"]] = ("stands", reason)
        elif not e.get("outcome") and not ruled_out and xg >= 0.25 and h % 100 < 35:
            plan[e["seq"]] = ("ruled_out", reason)
            ruled_out = True
    return plan


async def replay(data: DemoData, match_id: str, on_event: OnEvent, minute_seconds: float,
                 start_minute: float = 0.0, stop: asyncio.Event | None = None) -> None:
    events = data.events_for(match_id)
    var = var_plan(match_id, events)
    ht = next((e["clock"] for e in events if e["type"] == "half_time"), 45.0)
    added_1h = max(0.0, ht - 45)
    last = 0.0
    await on_event(match_id, {"type": "match_reset", "match_id": match_id})
    for e in events:
        if stop is not None and stop.is_set():
            return
        elapsed = e["clock"] if e["period"] == 1 else e["clock"] + added_1h
        if elapsed >= start_minute:
            wait = (elapsed - max(last, start_minute)) * minute_seconds
            if wait > 0:
                await asyncio.sleep(wait)
        last = elapsed
        if e["seq"] in var and elapsed >= start_minute:
            # The ball is in the net, VAR checks (the clock stops), then the decision. VAR events carry no seq,
            # so they never collide with the match's own event numbering.
            decision, reason = var[e["seq"]]
            base = {"period": e["period"], "clock": e["clock"], "team_id": e.get("team_id"),
                    "player_id": e.get("player_id"), "xg": e.get("xg"), "reason": reason}
            await on_event(match_id, {"type": "var_check", **base})
            await asyncio.sleep(max(VAR_MIN_SECONDS, 3 * minute_seconds))
            if stop is not None and stop.is_set():
                return
            await on_event(match_id, {"type": "var_decision", **base, "decision": decision})
            if decision == "ruled_out":
                e = {**e, "var_disallowed": True}
        await on_event(match_id, e)
        if e["type"] == "half_time" and elapsed >= start_minute:
            await asyncio.sleep(HALF_TIME_BREAK_SECONDS)


class Scheduler:
    """Keeps the featured matches playing on a loop, staggered so something is always live."""

    def __init__(self, data: DemoData, on_event: OnEvent, cfg: Settings = settings):
        self.data, self.on_event, self.cfg = data, on_event, cfg
        self.tasks: dict[str, asyncio.Task] = {}
        self.stops: dict[str, asyncio.Event] = {}

    def start(self) -> None:
        for i, mid in enumerate(self.cfg.featured_matches):
            if mid in self.data.matches:
                self.tasks[mid] = asyncio.create_task(self._loop(mid, i * self.cfg.stagger_seconds))

    async def _loop(self, mid: str, delay: float) -> None:
        await asyncio.sleep(delay)
        while True:
            stop = asyncio.Event()
            self.stops[mid] = stop
            try:
                await replay(self.data, mid, self.on_event, self.cfg.minute_seconds, stop=stop)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                log.exception("replay failed for %s", mid)
            await asyncio.sleep(self.cfg.restart_pause_seconds)

    async def restart(self, mid: str, start_minute: float = 0.0, minute_seconds: float | None = None) -> None:
        """Restart one match now (used to record the demo from a chosen minute)."""
        if mid in self.tasks:
            self.tasks[mid].cancel()
        if mid in self.stops:
            self.stops[mid].set()

        async def run() -> None:
            await replay(self.data, mid, self.on_event, minute_seconds or self.cfg.minute_seconds,
                         start_minute=start_minute)
            await asyncio.sleep(self.cfg.restart_pause_seconds)
            await self._loop(mid, 0)

        self.tasks[mid] = asyncio.create_task(run())


# ----------------------------------------------------------- Azure Event Hubs
async def publish_forever(cfg: Settings = settings) -> None:
    from azure.eventhub import EventData
    from azure.eventhub.aio import EventHubProducerClient
    from azure.identity.aio import DefaultAzureCredential

    data = DemoData(cfg.data_dir)
    cred = DefaultAzureCredential(managed_identity_client_id=cfg.managed_identity_client_id or None)
    producer = EventHubProducerClient(cfg.eventhub_namespace, cfg.eventhub_name, credential=cred)

    sent = 0

    async def send(match_id: str, ev: dict) -> None:
        nonlocal sent
        batch = await producer.create_batch(partition_key=match_id)
        batch.add(EventData(json.dumps({"match_id": match_id, **ev}, default=float)))
        await producer.send_batch(batch)
        sent += 1
        if sent == 1 or sent % 500 == 0:
            log.info("published %d events to %s/%s", sent, cfg.eventhub_namespace, cfg.eventhub_name)

    log.info("Match Feed starting: %d featured matches -> %s/%s",
             len(cfg.featured_matches), cfg.eventhub_namespace, cfg.eventhub_name)
    async with producer:
        Scheduler(data, send, cfg).start()
        await asyncio.Event().wait()


async def consume_forever(on_event: OnEvent, cfg: Settings = settings,
                          on_received: Callable[[], None] | None = None) -> None:
    """Consume match events from Event Hubs, reconnecting with backoff if the client ever stops."""
    from azure.eventhub.aio import EventHubConsumerClient
    from azure.identity.aio import DefaultAzureCredential

    received = 0

    async def handle(partition_context, event) -> None:
        nonlocal received
        if event is None:
            return
        body = json.loads(event.body_as_str())
        received += 1
        if received == 1 or received % 500 == 0:
            log.info("received %d events from Event Hubs", received)
        if on_received:
            on_received()
        await on_event(body.pop("match_id"), body)

    async def on_error(partition_context, error) -> None:
        pid = getattr(partition_context, "partition_id", "-")
        log.warning("Event Hubs consumer error (partition %s): %r", pid, error)

    backoff = 5.0
    while True:
        try:
            cred = DefaultAzureCredential(managed_identity_client_id=cfg.managed_identity_client_id or None)
            consumer = EventHubConsumerClient(fully_qualified_namespace=cfg.eventhub_namespace,
                                              eventhub_name=cfg.eventhub_name,
                                              consumer_group=cfg.eventhub_consumer_group, credential=cred)
            log.info("Event Hubs consumer connecting to %s/%s", cfg.eventhub_namespace, cfg.eventhub_name)
            async with consumer, cred:
                await consumer.receive(on_event=handle, on_error=on_error, starting_position="@latest")
            log.warning("Event Hubs consumer stopped; reconnecting")
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("Event Hubs consumer failed; retrying in %.0fs", backoff)
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60.0)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(publish_forever())
