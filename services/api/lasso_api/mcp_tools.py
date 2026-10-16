"""The Gaffer as an MCP server.

Every agent reaches live match intelligence through these tools (streamable
HTTP at ``/mcp``), so the model is a shared, auditable capability rather than
something each agent re-implements. Any MCP client, for example GitHub
Copilot or the Foundry agent playground, can use the same tools.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from lasso_engine.explain import shapley
from lasso_engine.markets import generate_markets

from .matchroom import MatchRoom

INSTRUCTIONS = (
    "Live football match intelligence from the Gaffer, a Bayesian in-play model. Probabilities are "
    "calibrated. The Gaffer's Gauge is each side's chance of winning, plus the draw. Explanations use exact "
    "Shapley attribution across goals, red cards, chances (xG) and the clock. All data is synthetic."
)


def build_mcp(rooms: dict[str, MatchRoom]) -> FastMCP:
    mcp = FastMCP("lasso-gaffer", instructions=INSTRUCTIONS, stateless_http=True, json_response=True,
                  streamable_http_path="/",
                  transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))

    def room(match_id: str) -> MatchRoom:
        if match_id not in rooms:
            raise ValueError(f"unknown match_id {match_id}; call list_live_matches first")
        return rooms[match_id]

    @mcp.tool()
    def list_live_matches() -> list[dict]:
        """List matches with status, score, minute and the current Gaffer's Gauge."""
        return [{k: r.summary()[k] for k in ("match_id", "status", "score", "minute", "probs")}
                | {"home": r.names[0], "away": r.names[1]} for r in rooms.values()]

    @mcp.tool()
    def gaffers_gauge(match_id: str) -> dict:
        """Current win/draw/loss probabilities, score, minute, red cards and xG for a match,
        plus the pre-match probabilities for comparison."""
        r = room(match_id)
        s = r.state
        return {**r.summary(), "xg": [round(x, 2) for x in s.xg],
                "expected_goals_remaining": {k: round(v, 2) for k, v in r.gaffer.probabilities(s).items()
                                             if k.endswith("remaining")}}

    @mcp.tool()
    def why_it_moved(match_id: str) -> dict:
        """Explain the change in each side's win chance since the last published moment, using exact
        Shapley attribution (goals, red_cards, chances, clock; values in percentage points that sum to the
        total change). Also returns the goals and red cards in that window."""
        r = room(match_id)
        out = {"since_minute": int(r.last_moment_state.clock), "now_minute": r.minute(), "sides": {}}
        for side in ("home", "away"):
            att = shapley(r.gaffer, r.last_moment_state, r.state, side)
            out["sides"][side] = {
                "team": r.names[0 if side == "home" else 1], "before_pct": round(att.before * 100, 1),
                "after_pct": round(att.after * 100, 1),
                "contributions_pts": {k: round(v * 100, 1) for k, v in att.contributions.items()}}
        out["window"] = r.window
        out["latest_moments"] = [{k: m[k] for k in ("trigger", "minute", "drivers", "score")}
                                 for m in r.moments[-3:]]
        return out

    @mcp.tool()
    def match_story(match_id: str) -> list[dict]:
        """Every story Lasso has published in this match so far, oldest first: the minute, what happened
        (goal, red_card, swing, pulse, half_time, full_time), the score, the team in focus with its win chance
        before and after (in %), the two biggest drivers in points, and the headline."""
        r = room(match_id)
        out = []
        for m in r.moments:
            side = "home" if m["focus"] == 0 else "away"
            top = sorted(m["drivers"], key=lambda d: abs(float(d["delta"])), reverse=True)[:2]
            out.append({"minute": m["minute"], "trigger": m["trigger"], "score": m["score"],
                        "focus_team": r.names[m["focus"]], "chance_before_pct": round(100 * m["before"][side]),
                        "chance_after_pct": round(100 * m["after"][side]),
                        "drivers": [{"label": d["label"]["en"], "points": round(float(d["delta"]), 1)} for d in top],
                        "headline": (m.get("headline") or {}).get("en", "")})
        return out

    @mcp.tool()
    def chances_at(match_id: str, minute: int) -> dict:
        """The Gaffer's Gauge as it stood at a given match minute (0 to 90+): each side's win chance and the
        draw, in %. Minute 45 means the end of the first half."""
        r = room(match_id)
        if minute > r.minute() and not r.state.finished:
            return {"minute": minute, "note": f"not played yet; the match is at minute {r.minute()}",
                    "chances_now_pct": {r.names[0]: round(100 * r.probs()["home"]),
                                        "draw": round(100 * r.probs()["draw"]),
                                        r.names[1]: round(100 * r.probs()["away"])}}
        period = 1 if minute <= 45 else 2
        past = [p for p in r.history if (p["period"], p["clock"]) <= (period, float(minute))]
        p = past[-1] if past else r.summary()["prematch"]
        return {"minute": minute if past else 0, "note": "" if past else "before kickoff",
                "chances_pct": {r.names[0]: round(100 * p["home"]), "draw": round(100 * p["draw"]),
                                r.names[1]: round(100 * p["away"])}}

    @mcp.tool()
    def match_stats(match_id: str) -> dict:
        """Team stats: possession, field tilt, pass accuracy and difficulty, shots, xG, xG in the last
        10 minutes (momentum), fastest shot speed, longest pass, cards and corners."""
        return room(match_id).stats_public()

    @mcp.tool()
    def recent_events(match_id: str, limit: int = 12) -> list[dict]:
        """The most recent notable events (goals, big chances, cards, substitutions)."""
        return room(match_id).feed[-max(1, min(limit, 40)):]

    @mcp.tool()
    def candidate_challenges(match_id: str) -> list[dict]:
        """Candidate 'Call It' micro-predictions for this moment, each option with the Gaffer's
        probability and biscuit payout multiplier."""
        r = room(match_id)
        return [m.to_dict() for m in generate_markets(r.gaffer, r.state, r.names[0], r.names[1])]

    @mcp.tool()
    def team_form(match_id: str) -> dict:
        """Pre-match expected goals for each side from the Bayesian team-strength model, and how the
        live posterior scoring rates have moved since kickoff."""
        r = room(match_id)
        s = r.state
        live = [r.gaffer.expected_rate(s, t) * r.data.params.expected_total_minutes for t in (0, 1)]
        return {"home": r.names[0], "away": r.names[1],
                "prematch_expected_goals": [round(r.pre["home_rate"], 2), round(r.pre["away_rate"], 2)],
                "live_scoring_rate_per_match": [round(x, 2) for x in live],
                "prematch_probs": r.summary()["prematch"]}

    @mcp.tool()
    def season_outlook(match_id: str) -> dict:
        """The league table as it stands (with this match's current score counted) and what the result
        means for the season: each club's title, top-four and relegation chances now, the race that matters
        most to each, and that chance if they win, draw or lose. From the rest of the season simulated
        10,000 times with the Gaffer's team strengths."""
        view = room(match_id).season_tool()
        return view or {"note": "the season outlook is still being calculated; try again in a few seconds"}

    return mcp
