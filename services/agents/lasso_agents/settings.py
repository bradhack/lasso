from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(k: str, d: str = "") -> str:
    return os.environ.get(k, d).strip()


@dataclass(frozen=True)
class AgentSettings:
    foundry_endpoint: str = field(default_factory=lambda: _env("FOUNDRY_PROJECT_ENDPOINT"))
    fast_model: str = field(default_factory=lambda: _env("FOUNDRY_MODEL", "gpt-4.1-mini"))
    writer_model: str = field(default_factory=lambda: _env("FOUNDRY_WRITER_MODEL", _env("FOUNDRY_MODEL", "gpt-4.1")))
    mcp_url: str = field(default_factory=lambda: _env("LASSO_MCP_URL", "http://localhost:8000/mcp/"))
    public_url: str = field(default_factory=lambda: _env("LASSO_AGENTS_PUBLIC_URL", "http://localhost:8100/"))
    client_id: str = field(default_factory=lambda: _env("AZURE_CLIENT_ID"))
    agent_timeout: float = field(default_factory=lambda: float(_env("LASSO_AGENT_TIMEOUT", "25")))


settings = AgentSettings()
