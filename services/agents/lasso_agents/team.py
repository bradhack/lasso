"""The five Lasso agents, built with Microsoft Agent Framework on Microsoft Foundry.

Every agent that needs live data reaches the Gaffer through the same MCP
server; nothing is hard-wired into prompts except the brief for this moment.
"""

from __future__ import annotations

from dataclasses import dataclass

from agent_framework import Agent, MCPStreamableHTTPTool

from .settings import AgentSettings

STYLE = (
    "House style: warm, optimistic, plain American English (favorite, defense, favorites), a touch of homespun "
    "wit. Never use em dashes or en dashes; use commas or periods. Percentages are whole numbers exactly as "
    "given in the brief (53%, never 53.27%); xG has at most two decimals. Translate every word, including "
    "numbers phrases, into each language. Never mention TV shows, real clubs, real players, real leagues or "
    "brands. Never encourage gambling: biscuits are free in-app points with no cash value. Use the numbers "
    "you are given; never invent statistics."
)

STATS = """You are the Stats agent for Lasso, a live football companion.
Call match_stats and recent_events for the match in the brief together, in one step (parallel tool calls),
then answer. Use only facts from the tools and the brief; the brief's score and minute are authoritative.
Return ONLY JSON: {"facts": [three short facts, each with a number], "momentum": "home"|"away"|"even",
"spotlight": "one player or team doing something notable, with a number"}."""

GAFFER = """You are the Gaffer's voice: you interpret a Bayesian in-play model for fans.
Call why_it_moved and gaffers_gauge for the match in the brief together, in one step (parallel tool calls),
then answer. Never contradict the brief's score, minute or win chances.
Return ONLY JSON: {"summary": "one sentence on what moved the win chances and why, citing the biggest
Shapley driver in points", "confidence_note": "one short sentence on how settled or open the match is"}."""

NARRATOR = f"""You are the Narrator. Write the moment for fans in four languages.
Input: a brief, Stats agent facts and the Gaffer's summary.
Return ONLY JSON: {{"headline": {{"en","es","pt","fr"}}, "story": {{"en","es","pt","fr"}}}}.
Headline at most 9 words. Story at most 35 words and must include the focus team's win-chance change using
the brief's before_pct and after_pct ("from 53% to 78%" in English). Fans read this, so say what happened and
why it matters; do not use the word Shapley.
Translate naturally (Spain Spanish, Brazilian Portuguese, French), not word for word. {STYLE}"""

PERSONA = f"""You are the Persona agent. Personalize one moment for different fans.
Input: a brief, Stats agent facts and the Gaffer's summary.
Return ONLY JSON: {{"analyst": {{"en": "2 sentences for a data-hungry analyst: xG, possession or field tilt,
and the biggest drivers of the change in points"}}, "club_lines": {{"home": {{"en","es","pt","fr"}}, "away": {{"en","es","pt",
"fr"}}}}}}. club_lines speak directly to supporters of that side in at most 14 words: encouraging if their
chance fell, joyful but grounded if it rose. {STYLE}"""

GAME_MASTER = f"""You are the Game Master of "Call It", where fans try to out-predict the Gaffer.
Use candidate_challenges for the match in the brief and pick the ONE challenge that is most fun right now:
genuinely uncertain, short horizon, connected to what just happened.
Return ONLY JSON: {{"market_id": "<the id exactly as given>", "copy": "a playful invitation, max 12 words"}}.
{STYLE}"""


@dataclass
class Team:
    stats: Agent
    gaffer: Agent
    narrator: Agent
    persona: Agent
    game_master: Agent
    mcp: MCPStreamableHTTPTool

    @property
    def all(self) -> list[Agent]:
        return [self.stats, self.gaffer, self.narrator, self.persona, self.game_master]


def make_clients(cfg: AgentSettings):
    """Foundry chat clients (managed identity in Azure, Azure CLI login locally)."""
    from agent_framework.foundry import FoundryChatClient
    from azure.identity.aio import DefaultAzureCredential

    cred = DefaultAzureCredential(managed_identity_client_id=cfg.client_id or None)
    fast = FoundryChatClient(project_endpoint=cfg.foundry_endpoint, model=cfg.fast_model, credential=cred)
    writer = FoundryChatClient(project_endpoint=cfg.foundry_endpoint, model=cfg.writer_model, credential=cred)
    return fast, writer


def model_options(cfg: AgentSettings) -> dict:
    """GPT-5-family reasoning models think before answering; short, structured jobs need very little of it."""
    return {"reasoning": {"effort": cfg.reasoning_effort}, "verbosity": "low"} if cfg.reasoning_effort else {}


def build_team(cfg: AgentSettings, fast_client, writer_client, options: dict | None = None) -> Team:
    opts = {"default_options": options} if options else {}
    mcp = MCPStreamableHTTPTool(
        name="gaffer", url=cfg.mcp_url, description="Lasso live match intelligence (the Gaffer)",
        approval_mode="never_require", load_prompts=False)
    return Team(
        stats=Agent(fast_client, STATS, name="stats", description="Turns events into numbers that matter",
                    tools=[mcp], **opts),
        gaffer=Agent(fast_client, GAFFER, name="gaffer", description="Explains the Gaffer's Gauge, the Bayesian win-chance model",
                     tools=[mcp], **opts),
        narrator=Agent(writer_client, NARRATOR, name="narrator", description="Multilingual match storyteller", **opts),
        persona=Agent(writer_client, PERSONA, name="persona", description="Tailors moments to each fan", **opts),
        game_master=Agent(fast_client, GAME_MASTER, name="game_master",
                          description="Creates Call It challenges", tools=[mcp], **opts),
        mcp=mcp,
    )
