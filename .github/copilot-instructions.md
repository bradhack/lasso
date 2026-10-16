# Copilot instructions for Lasso

Lasso is a live, multi-agent football match companion built for the Microsoft and Premier League *Inside the Game* hackathon (submission deadline: Oct 27, 2026). It replays synthetic matches and updates a Bayesian win-probability model, **the Gaffer**, with every event. The model's output is the **Gaffer's Gauge**. Seven AI agents in two workflows explain each swing and answer fans' questions (Ask the Gaffer), and fans make free-to-play **Call It** predictions against the model.

Read `README.md`, `docs/model-report.md` and `docs/DEPLOY.md` before making non-trivial changes.

## Repository map

| Path | What lives there |
|---|---|
| `engine/lasso_engine/` | Synthetic league + event simulator (`league.py`, `simulator.py`), the Gaffer (`strength.py` pre-match, `inplay.py` live), Shapley explanations (`explain.py`), Call It pricing (`markets.py`), training/evaluation |
| `services/api/lasso_api/` | FastAPI app: match rooms (`matchroom.py`), game logic (`game.py`, `stickers.py`), the Gaffer **MCP server** (`mcp_tools.py`, mounted at `/mcp`), realtime hub (`realtime.py`), Match Feed (`feed.py`), A2A client (`agents_client.py`), Listen (`speech.py`). Agent evaluation: `services/api/tests/agent_eval.py` |
| `services/agents/lasso_agents/` | Microsoft Agent Framework agents (`team.py`), the Match Director fan-out/fan-in workflow and the Press Room (Ask the Gaffer) workflow (`director.py`), A2A server that routes between them (`server.py`) |
| `web/src/` | React 19 + TypeScript phone app (PWA) and broadcast overlay (`pages/Overlay.tsx`). Accessibility helpers: `useDialog.ts`, `setPageLang` in `i18n.ts`. Listen: `components/Listen.tsx` |
| `infra/` | Bicep for every Azure resource, deployed with `azd up` |
| `data/demo/` | Runtime data pack: held-out season events + trained model. `data/league/` is generated and git-ignored |

## How to run and test

```bash
pip install -e "engine[dev,eval]" -r services/api/requirements.txt -r services/agents/requirements.txt
cd engine && pytest -q                       # engine tests
cd services/agents && pytest -q              # workflow test with a scripted model (no cloud)
cd web && npm ci && npm run build            # type-check + build
cd services/api && uvicorn lasso_api.main:app --port 8000          # serves web/dist too
cd services/agents && uvicorn lasso_agents.server:app --port 8100  # offline mode unless FOUNDRY_PROJECT_ENDPOINT is set
python services/api/tests/integration_smoke.py   # end-to-end against a running API
python web/e2e/play.py                           # plays the app in a headless phone browser
```

Speed up local replays with `LASSO_MINUTE_SECONDS=0.5`. Point the API at the agents with `LASSO_AGENTS_URL=http://localhost:8100/`.

## Azure

- Deploy everything with `azd up` from the repo root. Images build remotely in ACR, so Docker isn't needed.
- Use the **Azure MCP Server** tools to inspect resources, read Container Apps logs and check role assignments before guessing at a fix.
- Auth is **keyless**: one user-assigned managed identity with RBAC data-plane roles. Local auth is disabled on Cosmos DB, Event Hubs, Web PubSub and Foundry. Never add connection strings, keys or secrets to code or Bicep. Add a role assignment instead.
- Model deployment names are Bicep parameters (`FOUNDRY_MODEL`, `FOUNDRY_WRITER_MODEL`). Check availability in the Foundry model catalog before changing them.
- The API runs as exactly **one replica**, because match rooms are in memory. Don't raise `maxReplicas` without moving room state out of process.

## Rules that must not be broken

1. **Synthetic data only.** The hackathon rules require it. Never add real clubs, players, leagues, crests or match data.
2. **The model never reads `truth/`.** Hidden club strengths and match form exist only for evaluation (`evaluate.py`). Training, the API and the agents must not load them.
3. **No real-money gambling.** Biscuits are free in-app points with no cash value and can't be bought. Don't add payments, cash-out, odds formats that imply betting (fractional/moneyline), or links to bookmakers.
4. **The app never waits on an LLM.** Every moment is published instantly from templates (`narrative.py`). Agent output arrives later and *replaces* it by `moment_id`. Keep that two-step pattern.
5. **Agents must stay time-boxed and cost-guarded.** Keep `run_agent` timeouts and the API's `_should_enrich` guard-rails (watched matches only, a per-match gap, a daily cap).
6. **Agents get live data through MCP**, not by importing engine code. New capabilities for agents become new tools in `mcp_tools.py` with clear docstrings, since those docstrings are what the model reads.
7. Agent prompts live in `services/agents/lasso_agents/team.py` and must ask for **JSON only**. Update `tests/test_director.py` when an output shape changes.
8. **Touchline adds no realtime messages.** Ball actions (`touches`) ride inside the Gauge `meter` message from `matchroom.py`. Keep them compact and keep them batched there; don't publish one message per pass.
9. **A realtime push must never block a match.** `realtime.py` sends with a short retry and a 3-second timeout, and skips groups nobody has joined. Keep that: an unbounded retry once froze every match when Web PubSub refused messages.
10. **Ask the Gaffer treats questions as data.** The Presser agent has no tools; the Scout's tools only read. The API puts the true events, numbers and rules into every question's brief, an off-topic ruling skips the writer, and answers are cleaned in code (`_localize`, `_plain_for_fans`, `_cap_words`). After changing any agent prompt, run `services/api/tests/agent_eval.py` and keep it passing.
11. **Listen reads only our own text.** `/api/speech/audio` takes a story or answer id, never text. Keep it that way, and keep the cache and daily cap.
12. **Accessibility is WCAG 2.2 AA.** Text colors must reach 4.5:1 contrast in both Midnight and Ivory (check new tokens in both). Sheets use `useDialog` (focus in, Tab trapped, Escape closes). Anything tappable is a `<button>` or has a role, a label and keyboard handling. Looping animations stop within 5 seconds. The page language follows the fan's (`setPageLang`). Re-run an axe-core audit after visual changes.

## Style

- **Python 3.12**, type hints everywhere, `from __future__ import annotations`, dataclasses or Pydantic models. Line length 110 (ruff). Async for I/O. Log with `logging`, never `print`, in services.
- **TypeScript** in strict mode. State lives in the zustand store (`web/src/store.ts`). No UI component libraries: styling is plain CSS with the tokens in `web/src/styles.css`.
- **Design language:** Midnight is the default (deep navy surfaces, silver for the home side and primary actions, brass gold for rewards and highlights); Ivory is the light mode. Use the color tokens in `styles.css`, never literal colors, so both themes work. Numbers use Barlow Condensed, body text DM Sans, the wordmark Sora. Touch targets are at least 44px. Respect `prefers-reduced-motion`.
- **User-facing copy:** American English (defense, favorite, color, halftime). Don't use em dashes. Keep the tone warm and plain. Nods to the show are fine (biscuits, the Gaffer, Believe, Diamond Dogs, the Goldfish), but never use the show's title, character names, quotes or logos.
- **Localization:** every user-facing string in `web/src/i18n.ts` and `narrative.py` needs EN, ES (Spain), PT (Brazil) and FR.
- Keep the engine deterministic for a given seed. If you change the simulator or the model, regenerate and re-evaluate (see the README), then update `docs/model-report.md` with the new numbers.

## Commits and pull requests

- Small, focused commits with imperative subjects ("Add comeback challenge copy").
- Run the relevant tests before committing. CI (`.github/workflows/ci.yml`) runs engine tests, agent tests, API imports, the web build and a Bicep build.
