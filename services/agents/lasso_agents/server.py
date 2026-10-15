"""Hosts the Match Director as an A2A agent (plus each specialist's agent card).

    uvicorn lasso_agents.server:app --port 8100
"""

from __future__ import annotations

import contextlib
import logging
import os

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from agent_framework.a2a import A2AExecutor
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from .director import build_director, build_press_room, parse_json
from .settings import settings
from .team import build_team, make_clients, model_options

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("lasso.agents")

if os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    # Every agent run, tool call and workflow step becomes an OpenTelemetry span in Application Insights
    # (and in the Foundry portal's tracing view once the project is connected to that resource).
    from agent_framework.observability import enable_instrumentation
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor()
    enable_instrumentation()
    log.info("OpenTelemetry tracing enabled")

if settings.foundry_endpoint:
    fast, writer = make_clients(settings)
else:  # local plumbing tests without a model deployment
    from .offline import OfflineChatClient

    log.warning("FOUNDRY_PROJECT_ENDPOINT not set: running agents in offline mode")
    fast = writer = OfflineChatClient()
_fast_agents = ("stats", "gaffer", "game_master", "scout")
team = build_team(settings, fast, writer,
                  model_options(settings) if settings.foundry_endpoint else None,
                  {a: (settings.fast_model if a in _fast_agents else settings.writer_model) if settings.foundry_endpoint
                   else "offline" for a in (*_fast_agents, "narrator", "persona", "presser")})


def new_director():
    """A fresh workflow per request: a workflow instance runs one request at a time, and goals in
    different matches can arrive together. Building one is cheap; the five agents are shared."""
    return build_director(team, settings.agent_timeout).as_agent(
        name="Match Director", description="Lasso's multi-agent moment producer")


def new_press_room():
    return build_press_room(team, settings.agent_timeout).as_agent(
        name="Press Room", description="Ask the Gaffer: answers fans' questions about a live match")


def route(context: RequestContext):
    """One A2A endpoint, two skills: a moment brief goes to the Director, a fan's question to the Press Room."""
    try:
        kind = parse_json(context.get_user_input()).get("kind")
    except Exception:  # noqa: BLE001
        kind = None
    return new_press_room() if kind == "ask" else new_director()


class DirectorExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        await A2AExecutor(route(context)).execute(context, event_queue)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await A2AExecutor(new_director()).cancel(context, event_queue)


card = AgentCard(
    name="Lasso Match Director",
    description="Turns a live football moment into a multilingual story, personal fan angles and a "
                "'Call It' challenge, using five cooperating agents and the Gaffer's Bayesian model over MCP. "
                "Also answers fans' questions about the match (Ask the Gaffer).",
    version="1.0.0",
    default_input_modes=["text"],
    default_output_modes=["text"],
    capabilities=AgentCapabilities(streaming=False),
    supported_interfaces=[AgentInterface(url=settings.public_url, protocol_binding="JSONRPC")],
    skills=[AgentSkill(id="produce_moment", name="Produce moment",
                       description="Input: JSON moment brief. Output: JSON moment package.",
                       tags=["football", "explainability", "multilingual", "gamification"]),
            AgentSkill(id="answer_question", name="Ask the Gaffer",
                       description='Input: JSON with "kind": "ask", the match and a fan\'s question. '
                                   "Output: JSON answer in the fan's language, with follow-up questions.",
                       tags=["football", "explainability", "multilingual", "q&a"])],
)
handler = DefaultRequestHandler(agent_executor=DirectorExecutor(), task_store=InMemoryTaskStore(),
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
