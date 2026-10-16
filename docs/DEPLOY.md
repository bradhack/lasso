# Deploying Lasso to Azure

One command provisions everything and deploys all three containers. The images are built in Azure Container Registry, so you don't need Docker locally.

## What gets created

| Resource | Purpose |
|---|---|
| Microsoft Foundry account + project `lasso` + model deployment(s) | The seven agents' models, and Azure AI Speech for Listen (the account is Azure AI Services, which includes Speech) |
| Container Apps environment + 3 apps (`api`, `agents`, `feed`) | API + MCP server + web app, the Match Director (A2A), the Match Feed |
| Container Registry (Basic) | Images, pulled by managed identity |
| Event Hubs (Basic) `match-events` | Live match event stream |
| Cosmos DB for NoSQL (serverless) `lasso` | Users, calls, leagues |
| Web PubSub (Standard S1) | Realtime push to phones and overlays. Keep it on Standard: the Free tier's 40,000 KB a day runs out after a few hours of testing |
| Log Analytics + Application Insights | Logs and OpenTelemetry traces for every agent step |
| User-assigned managed identity | Keyless access to all of the above. Local auth is disabled everywhere. |

Rough cost while it's running: about $7 to $10 a day with everything on, plus model tokens and speech (both small). Daily caps keep usage in check:

| Setting | Default | What it limits |
|---|---|---|
| `LASSO_AGENTS_DAILY_LIMIT` | 600 | Agent-written stories (they only run for matches someone is watching) |
| `LASSO_ASKS_DAILY_LIMIT` | 500 | Ask the Gaffer questions, across all fans |
| `LASSO_ASKS_PER_USER_DAILY` / `LASSO_ASKS_MIN_GAP` | 30 / 6s | Questions per fan per day, and the pace |
| `LASSO_SPEECH_DAILY_LIMIT` | 1500 | Listen clips synthesized (repeat plays come from a cache) |

## Steps

1. Install the [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) and the [Azure Developer CLI (azd)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd).
2. Sign in:
   ```bash
   az login
   azd auth login
   ```
3. Check that you have model quota in the region. In the Foundry portal, open **Quotas** for East US 2 and look for `gpt-5-mini` Global Standard. The templates request 50K tokens per minute.
4. From the repository root:
   ```bash
   azd env new lasso
   azd env set AZURE_LOCATION eastus2
   # optional: use a stronger model for the Narrator and Persona agents if your subscription has it
   # azd env set FOUNDRY_WRITER_MODEL <model-name>
   # azd env set FOUNDRY_WRITER_MODEL_VERSION <version>
   azd up
   ```
   The first run takes about 15 minutes. When it finishes, azd prints `LASSO_APP_URL`.
5. Open `LASSO_APP_URL` on your phone. Matches start a few seconds after the feed comes up, with a new one every 75 seconds, and they loop.
6. **Tracing in Foundry:** in the Foundry portal, open the project and go to **Tracing**, then connect the Application Insights resource `appi-lasso-…`. Each Match Director run shows up as a trace, with a span for every agent and MCP tool call.

## Updating an existing deployment

- **Code only:** `azd deploy api` and `azd deploy agents`. Run them in two terminals at once to halve the wait; remote builds start clean each time, so each takes about 4 to 8 minutes.
- **Infrastructure changes** (new roles or settings, such as Listen's Speech access): run `azd provision` first, then deploy. The agents key (only the API may run the agents) is one of these: until `azd provision` adds it to both apps, the agents service stays open as before, so the order doesn't break anything. New role assignments can take a few minutes to apply; until then Listen falls back to the phone's own voice.
- Open phones pick up a new version on their own within about 90 seconds.

## Useful commands

```bash
azd deploy agents                # redeploy one service
azd env get-values               # URLs, endpoints
# Restart the showcase match from minute 78 at 2 real seconds per match minute (for recording the demo):
curl -X POST -H "X-Admin-Key: <admin key>" "$LASSO_APP_URL/api/admin/matches/S5-MD07-03/restart?from_minute=78&minute_seconds=2"
# Add &agents=true to have the agents write that replay's stories even with no one watching (the evaluation uses it)
azd down --purge                 # tear everything down when judging ends (after Nov 10, 2026)
```

The admin key stays the same across provisions. Pin it to a value of your choice once with `azd env set LASSO_ADMIN_KEY <value>` (then `azd provision`); otherwise a stable key is derived for the environment. To read the current key (PowerShell):

```powershell
$rg = azd env get-value AZURE_RESOURCE_GROUP
az containerapp list -g $rg --query "[?starts_with(name,'ca-api-')].name" -o tsv   # the API app's name
az containerapp secret show -n <that name> -g $rg --secret-name admin-key --query value -o tsv
```
 During an admin restart, the API replays that match itself and ignores Event Hubs for it until the replay ends.

## Evaluate the agents

```bash
python services/api/tests/agent_eval.py "$LASSO_APP_URL" --key <admin key>
```

It replays the showcase match (about 8 minutes), asks 26 set questions from five test fans in four languages, checks every answer and every agent-written story against the match data, and writes `docs/agent-eval.md`. It restarts that match for anyone watching, so run it when no one is judging, and wait a minute after a deploy so the new version is serving. Standard library only.

## Run locally (no Azure needed)

```bash
# 1. API (engine + match rooms + MCP + game), serving the web app
pip install -e engine && pip install -r services/api/requirements.txt
cd web && npm ci && npm run build && cd ..
cd services/api && LASSO_AGENTS_URL=http://localhost:8100/ uvicorn lasso_api.main:app --port 8000

# 2. Agents (offline mode without FOUNDRY_PROJECT_ENDPOINT; set it plus `az login` to use real models)
cd services/agents && pip install -r requirements.txt && uvicorn lasso_agents.server:app --port 8100

# open http://localhost:8000 (phone app) or http://localhost:8000/#/overlay/S5-MD07-03 (broadcast overlay)
# Locally, Listen uses the browser's own voice, and the agents answer with the fallback text unless Foundry is set.
```
