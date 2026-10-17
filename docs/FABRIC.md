# Lasso in Microsoft Fabric

Lasso streams what its agents do into **Microsoft Fabric Real-Time Intelligence**, so the whole system can be watched as it runs: how fast the agents answer, how many tokens they use, which MCP tools they pick, what the code checks catch before fans see it, how the agents recover when one is slow, and how every match swung.

```
Lasso API ──(every story, answer and agent run)──> Eventstream ──> Eventhouse (KQL) ──> Real-Time Dashboard
```

- **What's sent:** one flat JSON event per agent-written story, per Ask the Gaffer answer, and per agent run inside them: timings, tokens, tools, the code checks' fixes, recoveries, the chances and the swing. Never a fan's question or answer text, and no fan ids. *Where:* `services/api/lasso_api/insights.py`.
- **Never in the way:** events go on a bounded queue and are sent in batches in the background. If Fabric is unreachable, events are dropped and the app carries on.
- **Off by default:** nothing is sent until `LASSO_FABRIC_CONNECTION` is set. The connection string is a Container Apps secret, never in the repo.
- **Fabric pieces:** the table and its mapping (`fabric/setup.kql`) and the dashboard's tiles (`fabric/dashboard.kql`).

![The Lasso agents dashboard in Fabric: stories and answers over time, answer times, each agent's time, tokens, what the code checks caught, how the agents recovered, the MCP tools chosen, the biggest swings, languages, two agents against one, and the Gaffer's Gauge](img/fabric-dashboard.png)

*The dashboard after two evaluation runs on the live app (the Press Room, then the single-agent baseline).*

## Set it up (about 30 minutes)

You need a Fabric workspace on a Fabric capacity (the 60-day Fabric trial works) and a work or school account in Microsoft Entra ID. A personal Microsoft account can't use Fabric; a user created in your Azure subscription's own directory (`you@yourdirectory.onmicrosoft.com`) can.

1. **Workspace.** In [Fabric](https://app.fabric.microsoft.com), create a workspace named **Lasso** on the Fabric trial (or a Fabric capacity).
2. **Eventhouse.** In the workspace, choose **New item**, then **Eventhouse**, named `lasso`. It comes with a KQL database named `lasso`.
3. **The table.** Open the `lasso` KQL database, choose **Query with code** (or open its queryset), paste all of `fabric/setup.kql`, click anywhere inside the command (below the comment lines) and choose **Run**. It's one script that creates the `LassoEvents` table and its JSON mapping.
4. **Eventstream.** Choose **New item**, then **Eventstream**, named `lasso-insights`.
   - **Add source**, then **Custom endpoint**, named `lasso-api`. Choose **Publish**.
   - Select the `lasso-api` source. On **Event Hub**, under **SAS Key Authentication**, copy **Connection string-primary key**.
5. **Point Lasso at it.** From the repo, with your azd environment selected:

   ```bash
   azd env set LASSO_FABRIC_CONNECTION "<the connection string>"
   azd provision
   azd deploy api
   ```

6. **Eventhouse destination.** Back in the Eventstream, choose **Edit**, then **Add destination**, then **Eventhouse**:
   - Data ingestion mode: **Event processing before ingestion**.
   - Workspace **Lasso**, Eventhouse **lasso**, KQL database **lasso**, existing table **LassoEvents**, input data format **JSON**.
   - Choose **Save**, then **Publish**.
7. **Some data.** Run the agent evaluation (it replays the showcase match and asks 27 questions; see [DEPLOY.md](DEPLOY.md#evaluate-the-agents)), or watch a match in the app. Then check in the KQL database:

   ```kusto
   LassoEvents | summarize count() by event_kind
   ```

8. **The dashboard.** Choose **New item**, then **Real-Time Dashboard**, named `Lasso agents`.
   - **New data source:** the `lasso` KQL database.
   - For each block in `fabric/dashboard.kql`, choose **Add tile**, paste the query, pick the visual named in its comment and **Apply**. Eleven tiles, about a minute each.
   - Set **Auto refresh** to 30 seconds and the time range to **Last 24 hours**.
9. **Share what you see.** Take a screenshot of the dashboard for `docs/img/fabric-dashboard.png`. Judges can't sign in to your Fabric tenant, so the screenshot and these queries are what they'll see.

## What the dashboard answers

| Tile | Question |
|---|---|
| Stories and answers over time | How busy are the agents? |
| How fast fans get answers | Typical and slowest answer times, every five minutes |
| Each agent's time | Which agent is the slow one? |
| Tokens per story and per answer | What does it cost? |
| What the code checks caught | Which slips do the agents make, and how often? |
| How the agents recovered | Timeouts, second tries, retries, recovered replies |
| Which MCP tools the agents chose | Does the Scout pick the right tools? |
| The biggest swings | The match moments that moved the Gauge most, with the agents' headlines |
| Two agents or one | The Press Room against the single-agent baseline, after an evaluation with `--solo` |
| Questions by language | English, Spanish, Portuguese and French |
| The Gaffer's Gauge | Home, draw and away, story by story, for the latest match |

## Cost

The Fabric trial is free for 60 days. On a paid capacity, the smallest (F2) is about $0.36 an hour pay-as-you-go and can be paused when it isn't needed. Sending the events costs nothing on the Lasso side.
