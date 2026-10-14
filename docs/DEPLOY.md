# Deploying Lasso to Azure

One command provisions everything and deploys all three containers. The images are built in Azure Container Registry, so you don't need Docker locally.

## What gets created

| Resource | Purpose |
|---|---|
| Microsoft Foundry account + project `lasso` + model deployment(s) | The five agents' models |
| Container Apps environment + 3 apps (`api`, `agents`, `feed`) | API + MCP server + web app, the Match Director (A2A), the Match Feed |
| Container Registry (Basic) | Images, pulled by managed identity |
| Event Hubs (Basic) `match-events` | Live match event stream |
| Cosmos DB for NoSQL (serverless) `lasso` | Users, calls, leagues |
| Web PubSub (Standard S1) | Realtime push to phones and overlays |
| Log Analytics + Application Insights | Logs and OpenTelemetry traces for every agent step |
| User-assigned managed identity | Keyless access to all of the above. Local auth is disabled everywhere. |

Rough cost while it's running: about $3 to $5 a day, plus model tokens. The API caps agent calls at 600 a day by default (`LASSO_AGENTS_DAILY_LIMIT`), and the agents only run for matches someone is watching.

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

## Useful commands

```bash
azd deploy agents                # redeploy one service
azd env get-values               # URLs, endpoints
# Restart the showcase match from minute 78 at 2 real seconds per match minute (for recording the demo):
curl -X POST "$LASSO_APP_URL/api/admin/matches/S5-MD07-03/restart?key=<admin key>&from_minute=78&minute_seconds=2"
azd down --purge                 # tear everything down when judging ends (after Nov 10, 2026)
```

The admin key is generated at provision time. To read it, run `az containerapp secret show -n ca-api-<token> -g rg-lasso --secret-name admin-key`. During an admin restart, the API replays that match itself and ignores Event Hubs for it until the replay ends.

## Run locally (no Azure needed)

```bash
# 1. API (engine + match rooms + MCP + game), serving the web app
pip install -e engine && pip install -r services/api/requirements.txt
cd web && npm ci && npm run build && cd ..
cd services/api && LASSO_AGENTS_URL=http://localhost:8100/ uvicorn lasso_api.main:app --port 8000

# 2. Agents (offline mode without FOUNDRY_PROJECT_ENDPOINT; set it plus `az login` to use real models)
cd services/agents && pip install -r requirements.txt && uvicorn lasso_agents.server:app --port 8100

# open http://localhost:8000 (phone app) or http://localhost:8000/#/overlay/S5-MD07-03 (broadcast overlay)
```
