"""Runtime settings, all from environment variables (12-factor)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(_env("LASSO_DATA_DIR", "../../data/demo")).resolve())
    web_dist: Path = field(default_factory=lambda: Path(_env("LASSO_WEB_DIST", "../../web/dist")).resolve())
    # Replay pacing: real seconds per match minute (4s => a match lasts ~6.5 minutes).
    minute_seconds: float = field(default_factory=lambda: float(_env("LASSO_MINUTE_SECONDS", "4")))
    featured_matches: tuple[str, ...] = field(default_factory=lambda: tuple(
        m for m in _env("LASSO_FEATURED_MATCHES",
                        "S5-MD07-03,S5-MD12-04,S5-MD21-07,S5-MD30-02").split(",") if m))
    stagger_seconds: float = field(default_factory=lambda: float(_env("LASSO_STAGGER_SECONDS", "75")))
    restart_pause_seconds: float = field(default_factory=lambda: float(_env("LASSO_RESTART_PAUSE", "45")))
    admin_key: str = field(default_factory=lambda: _env("LASSO_ADMIN_KEY", "lasso-local"))

    # Event source: "local" (in-process replay) or "eventhubs" (consume from Azure Event Hubs).
    event_source: str = field(default_factory=lambda: _env("LASSO_EVENT_SOURCE", "local"))
    eventhub_namespace: str = field(default_factory=lambda: _env("EVENTHUB_FULLY_QUALIFIED_NAMESPACE"))
    eventhub_name: str = field(default_factory=lambda: _env("EVENTHUB_NAME", "match-events"))
    # Seconds of Event Hubs silence before the API plays matches itself (0 disables the fallback).
    feed_fallback_seconds: float = field(default_factory=lambda: float(_env("LASSO_FEED_FALLBACK_SECONDS", "120")))
    eventhub_consumer_group: str = field(default_factory=lambda: _env("EVENTHUB_CONSUMER_GROUP", "$Default"))

    # Realtime: "local" websocket or Azure Web PubSub.
    webpubsub_endpoint: str = field(default_factory=lambda: _env("WEBPUBSUB_ENDPOINT"))
    webpubsub_hub: str = field(default_factory=lambda: _env("WEBPUBSUB_HUB", "lasso"))

    # Persistence: in-memory unless a Cosmos DB endpoint is configured.
    cosmos_endpoint: str = field(default_factory=lambda: _env("COSMOS_ENDPOINT"))
    cosmos_database: str = field(default_factory=lambda: _env("COSMOS_DATABASE", "lasso"))

    # Agents service (A2A). Empty => built-in template narration only.
    agents_url: str = field(default_factory=lambda: _env("LASSO_AGENTS_URL"))
    agents_timeout: float = field(default_factory=lambda: float(_env("LASSO_AGENTS_TIMEOUT", "40")))
    # Cost guard-rails: only enrich watched matches, at most one call per match per N seconds, and a daily cap.
    agents_min_gap_seconds: float = field(default_factory=lambda: float(_env("LASSO_AGENTS_MIN_GAP", "20")))
    agents_daily_limit: int = field(default_factory=lambda: int(_env("LASSO_AGENTS_DAILY_LIMIT", "600")))

    managed_identity_client_id: str = field(default_factory=lambda: _env("AZURE_CLIENT_ID"))


settings = Settings()
