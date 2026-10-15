# Lasso for judges

Everything below points at something you can open: a screen in the live app, a file in this repo, or a number from the [model report](model-report.md).

- **Live app:** https://ca-api-eq6gno2m4qr7w.jollyrock-1439cd71.eastus2.azurecontainerapps.io (works best on a phone, or a narrow browser window)
- **Demo video (under 2 minutes):** <!-- VIDEO LINK --> linked from the submission page
- **Category:** Best Multi-Agent System

## A two-minute tour

The app replays four synthetic matches on a loop, so something is always live. Each match takes about six and a half minutes, and they start a little over a minute apart. The showcase is **Eastholme Rangers v Brackenford City**: a goal down in the 1st minute, down to ten men in the 5th, level in the 14th, and the winner in the 82nd.

1. Open the link, pick a fan name and a club (choose **Eastholme Rangers** for the full story), then **Fan** or **Analyst**.
2. Open a live match. The **Gaffer's Gauge** shows each side's chances, updated with every event. **Touchline** shows the ball on the pitch; switch to **Shots** for the shot map.
3. Read **Why it moved**, then tap **AI agents ›**. **Under the hood** shows which agents wrote that story, which ran in parallel, every MCP tool they called and their time, tokens and model.
4. In **Ask the Gaffer**, tap a suggestion or type a question in any of the four languages. Tap the agents line under the answer to see which tools the Scout chose.
5. **Call it:** pick an option and lasso it. You are betting free biscuits against the Gaffer's own odds.
6. If your club falls behind, **Touch the sign**. If they draw level, every believer gets a bonus.
7. Scroll to **Match story** for every story told so far. Visit **Stickers** and **Me** for the sticker book, call history, language (EN, ES, PT, FR) and light or dark mode.
8. For broadcasters: open `#/overlay/S5-MD07-03` for a transparent overlay you can lay over a video feed.

## 1. Technical implementation

| What | Where to check |
|---|---|
| A synthetic league: 20 clubs, about 480 players, five seasons, 1,900 matches and 2.2M events, with a hidden "truth" to test against | `engine/lasso_engine/league.py`, `simulator.py`; [model report §1](model-report.md#1-the-synthetic-league) |
| **The Gaffer:** a Bayesian hierarchical Poisson model for pre-match strength, plus Gamma-Poisson live updating from xG, cards and game state | `engine/lasso_engine/strength.py`, `inplay.py` |
| Exact Shapley attribution for every swing ("the red card cost 25 points") | `engine/lasso_engine/explain.py` |
| Event streaming: Match Feed → Azure Event Hubs → API, with reconnect and backoff, duplicate-safe replay and catch-up after a restart, and an automatic in-process fallback if the hub goes quiet | `services/api/lasso_api/feed.py`, `main.py` (`on_event`, `_feed_watchdog`) |
| Realtime to phones through Azure Web PubSub. Ball positions ride inside the once-a-second Gauge update, so Touchline adds no messages | `services/api/lasso_api/realtime.py`, `matchroom.py` |
| The whole stack in Bicep with keyless managed identity, deployed with `azd up` | `infra/`, [deploy guide](DEPLOY.md) |
| CI on every push: engine tests, agent workflow tests with a scripted model, API import check, web type-check and build, Bicep build | `.github/workflows/ci.yml` |
| End-to-end checks: a smoke test against a running API (realtime, calls, the story endpoint, Ask the Gaffer, MCP) and a headless phone run of the app | `services/api/tests/integration_smoke.py`, `web/e2e/play.py` |

**Numbers** (held-out season 5, 380 matches; see the [model report](model-report.md)):

- The Gaffer captures **85%** of the achievable pre-match improvement over base rates (ranked probability score 0.2025, against 0.2256 for base rates and 0.1982 for an oracle that knows the hidden strengths).
- The live Gauge is calibrated to within **1.5 points** on average: when it says 30%, it happens about 30% of the time.
- It recovers the hidden team strengths with correlations of **0.95** (attack) and **0.91** (defense).
- The fast Laplace posterior matches full NUTS MCMC (posterior means correlate at **0.99996**).
- The Gauge and an instant story reach phones in **under a second**. The agents' version follows a few seconds later, so the app never waits on a language model.

## 2. Agentic design

Seven agents, built with **Microsoft Agent Framework** on **Microsoft Foundry**, in two workflows behind one **A2A** endpoint. Every live number they use comes from the Gaffer through **MCP**.

**Match Director** (a story for every goal, red card, big swing and half): five agents in two rounds.

| Round | Agent | Job | MCP tools |
|---|---|---|---|
| 1, in parallel | Stats | The numbers that matter | `match_stats`, `recent_events` |
| 1, in parallel | Gaffer | Why the chances moved | `why_it_moved`, `gaffers_gauge` |
| 2, in parallel | Narrator | The story in EN, ES, PT and FR | none |
| 2, in parallel | Persona | Fan and analyst angles, a line for each club's supporters, a halftime team talk | none |
| 2, in parallel | Game Master | Picks the next Call It challenge | `candidate_challenges` |

**Press Room** (Ask the Gaffer): two agents in sequence. The **Scout** reads the question and chooses up to three of the Gaffer's tools (`chances_at`, `match_story`, `why_it_moved` and others), calling them in parallel. The **Gaffer** then answers in the fan's language from the Scout's notes, with no tools of its own.

Design choices worth a look:

- **Agents explain; the model decides.** Probabilities, drivers and odds come from the Bayesian model over MCP. The agents are told never to invent statistics, and the API always passes the authoritative score, minute, chances and event list.
- **The app never waits on a model.** Every story starts as an instant template; the agents' version replaces it when it arrives. Every agent call is time-boxed, and a failed agent only removes its own part.
- **Right-sized models.** Short, structured jobs run with minimal reasoning and low verbosity, which took a story from about 30 seconds to under 15.
- **Shared tools, not copied logic.** The nine MCP tools are the one way any agent, or any outside MCP client such as GitHub Copilot, reaches live match intelligence.
- **Observable.** Every agent run records its round, start time, tools (with arguments), tokens and model. That trace is shown in the app (**Under the hood**) and exported to Application Insights through OpenTelemetry.

Where to check: `services/agents/lasso_agents/director.py` (both workflows), `team.py` (the seven agents and their instructions), `server.py` (A2A routing and the agent card at `/.well-known/agent-card.json`), `services/api/lasso_api/mcp_tools.py` (the MCP server), `services/api/lasso_api/agents_client.py` (the A2A client).

## 3. Real-world impact

- **Second screen for broadcast and streaming.** Lasso tells a viewer what just changed and why, in a sentence, the moment it happens. The transparent overlay (`#/overlay/<match>`) puts the same Gauge on a broadcast.
- **Understanding, not just numbers.** Every swing comes with its causes in plain English. Fans get the two biggest reasons; analysts get every driver in points, xG and field tilt. Ask the Gaffer answers anything else.
- **For every fan.** Four languages, fan or analyst depth, your club's angle, light and dark themes, and respect for reduced-motion settings.
- **Engagement without gambling.** Biscuits are free points with no cash value and cannot be bought, with a daily top-up so nobody is locked out. The calibration bonus uses a proper scoring rule, so stating your true confidence is always the best strategy.
- **Honest probabilities.** The Gauge is tested on a season it never saw, and the [model report](model-report.md) publishes how well it does.
- **Affordable to run.** Agents only run for matches someone is watching, with a per-match gap, a daily cap and per-fan limits on questions. The whole stack costs about $7 to $10 a day with everything on.

## 4. User experience and demo

- A phone-first PWA that installs to the home screen, with the Midnight theme and an Ivory light mode.
- The match page in order: scoreboard with bookings, Gaffer's Gauge, Touch the sign, Touchline, Why it moved, Call it, Ask the Gaffer, Match story, stats and the event feed.
- Game features: streaks with the **Goldfish** (one miss a week forgiven), a 17-sticker book, daily missions, friend leagues and a call history.
- Open phones pick up new deploys on their own.
- Twenty original club crests designed as one set (`web/scripts/make_crests.py`).

## 5. Category adherence: Best Multi-Agent System

- **Multiple specialized agents:** seven, each with one job, its own instructions and only the tools it needs.
- **Orchestration:** Agent Framework workflows with fan-out and fan-in (Match Director) and a sequential hand-off (Press Room).
- **Agent-to-agent protocol:** the API calls the agents over A2A; one endpoint offers two skills and routes each request to the right workflow.
- **Shared tools over MCP:** nine tools on the Gaffer's MCP server, used by four of the agents.
- **Resilience and safety:** time-boxed agents, graceful fallback, a fan's question treated as data (the agent that answers it has no tools), and cost caps.
- **Visible to users:** Under the hood shows each run, so the multi-agent system is something a fan can see, not just an architecture diagram.

## How it was built

Brad designed, directed and shipped Lasso, working with two AI assistants:

- **GitHub Copilot** in Agent Mode, with the **Azure MCP Server**, worked against the live Azure resources: deploying, reading logs and fixing infrastructure. It found and fixed an Event Hubs consumer bug from the container logs (commit `f525983`) and a Foundry deployment ordering issue in Bicep (`4967f0c`). Its repository guidance is in `.github/copilot-instructions.md`.
- **Claude** helped with design and much of the code: the synthetic league and the scripts that replay matches into the live feed, the Gaffer model and its evaluation, the agents, the app, the club crests and the submission images.

Every commit records its co-authors.

## Data

All clubs, players, crests and matches are synthetic, as the rules require. Nothing in the repo uses real teams, players, leagues or brands.
