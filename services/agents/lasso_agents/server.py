"""Hosts the Match Director as an A2A agent (plus each specialist's agent card).

    uvicorn lasso_agents.server:app --port 8100
"""

from __future__ import annotations

import contextlib
import logging

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from agent_framework.a2a import A2AExecutor
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from .director import build_director
from .settings import settings
from .team import build_team, make_clients

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("lasso.agents")

if settings.foundry_endpoint:
    fast, writer = make_clients(settings)
else:  # local plumbing tests without a model deployment
    from .offline import OfflineChatClient

    log.warning("FOUNDRY_PROJECT_ENDPOINT not set: running agents in offline mode")
    fast = writer = OfflineChatClient()
team = build_team(settings, fast, writer)
director = build_director(team, settings.agent_timeout).as_agent(
    name="Match Director", description="Lasso's multi-agent moment producer")

card = AgentCard(
    name="Lasso Match Director",
    description="Turns a live football moment into a multilingual story, personal fan angles and a "
                "'Call It' challenge, using five cooperating agents and the Gaffer's Bayesian model over MCP.",
    version="1.0.0",
    default_input_modes=["text"],
    default_output_modes=["text"],
    capabilities=AgentCapabilities(streaming=False),
    supported_interfaces=[AgentInterface(url=settings.public_url, protocol_binding="JSONRPC")],
    skills=[AgentSkill(id="produce_moment", name="Produce moment",
                       description="Input: JSON moment brief. Output: JSON moment package.",
                       tags=["football", "explainability", "multilingual", "gamification"])],
)
handler = DefaultRequestHandler(agent_executor=A2AExecutor(director), task_store=InMemoryTaskStore(),
                                agent_card=card)


async def health(_request):
    return JSONResponse({"ok": True, "agents": [a.name for a in team.all], "mcp": settings.mcp_url,
                         "foundry": bool(settings.foundry_endpoint)})


@contextlib.asynccontextmanager
async def lifespan(_app):
    try:
        await team.mcp.connect()
        log.info("connected to Gaffer MCP at %s", settings.mcp_url)
    except Exception as e:  # noqa: BLE001
        log.warning("MCP not reachable yet (%s); agents will retry on first use", e)
    yield
    with contextlib.suppress(Exception):
        await team.mcp.close()


app = Starlette(
    routes=[Route("/health", health), *create_agent_card_routes(card), *create_jsonrpc_routes(handler, "/")],
    lifespan=lifespan,
)
