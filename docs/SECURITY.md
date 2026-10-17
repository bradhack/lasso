# Security

Lasso has no passwords or payment details, and fans don't create accounts. What needs protecting is our Azure bill, the fans' game progress and the agents' honesty. This page says how each is protected, what the last scan found, and how to run the scans yourself.

## What protects what

| Risk | Protection |
|---|---|
| Someone runs the AI agents directly and runs up the bill | The agents service only runs for requests carrying the API's shared key (`LASSO_AGENTS_KEY`, a Container Apps secret on both apps). Its agent cards and health check stay public for judges. |
| Someone acts as another fan | A fan's id is the only thing that identifies them, so it's never shown to other fans: leaderboards carry an opaque row key and a "me" flag, and league responses list no members. |
| Cost from heavy use | Agents run only for matches someone is watching, with a daily cap on stories, questions and spoken clips, a pace per fan, a cap on private replays, and a cap on sign-ups (30 per address per hour, 5,000 a day). |
| Trick questions ("ignore your instructions") | A question is something to answer, never an order. The agent that writes answers can't take actions; the Scout can only read match data. The evaluation includes an injection test. |
| Made-up facts | Answers are checked in code before a fan sees them: real club names, a percentage given to the wrong team, and xG for fans are removed. |
| Reading arbitrary text aloud | Listen takes the id of a story, event or answer (or a fixed voice sample), never text, and only voices from our own list. |
| Leaked keys | No keys in the code. Cosmos DB, Event Hubs, Web PubSub and Foundry (including Speech) have key-based sign-in turned off and are reached with a managed identity. The only secrets (the admin key and the agents key) live as Container Apps secrets. The admin key goes in an `X-Admin-Key` header, so it stays out of access logs, and it's compared in constant time. |
| Containers | They run as a non-root user, and the registry has its admin account turned off. |

## Last scan (October 16, 2026)

| Scan | Tool | Result |
|---|---|---|
| Web dependencies | `npm audit` | 0 vulnerabilities |
| Python dependencies (API, agents, engine) | `pip-audit` | 0 known vulnerabilities |
| Python code | `bandit` | 0 medium or high; 4 low, all expected (random numbers for the rival bots, a football "pass" read as a password) |
| Secrets in the code and its history | `detect-secrets`, plus a search of the git history | None (one false alarm: a reference to a secret by name) |
| Azure templates and Dockerfiles | `checkov` | Remaining findings are enterprise network isolation (private endpoints, image quarantine) that a public demo doesn't use |
| Manual review | | Found and fixed: the agents service open to anyone, fans' ids on the leaderboard, the admin key in the URL, unlimited sign-ups |

## Accepted findings

The security workflow reports these on purpose; each is dismissed as "Won't fix" in code scanning, for this reason:

| Finding | Tool | Why it stays |
|---|---|---|
| Disable public access; private endpoints for Foundry, Cosmos DB and the Container Apps environment | Template Analyzer, checkov | Lasso is a public demo with no virtual network. Every service accepts only Microsoft Entra sign-in (keys are off), which is what protects them. |
| Image quarantine and vulnerability scanning in the registry | checkov | Needs the Premium registry or Defender for Containers; dependencies are scanned in this workflow and by `pip-audit` and `npm audit`. |
| Restrict Cognitive Services endpoints | Template Analyzer | As above: no virtual network, Entra-only sign-in. |

## Run the scans yourself

From the repo root:

```
npm --prefix web audit
pip install pip-audit bandit detect-secrets checkov
pip-audit -r services/api/requirements.txt
pip-audit -r services/agents/requirements.txt
pip-audit engine
bandit -r services engine -x "*/tests/*"
detect-secrets scan --exclude-files "(node_modules|dist|data/)" .
checkov -d infra --framework bicep
```

In VS Code, these extensions scan as you work:

- **SonarQube for IDE** (SonarSource): code quality and security issues as you type, no account needed.
- **Snyk Security**: dependencies and code, with fixes suggested inline (free account).

Microsoft Security DevOps isn't a VS Code extension; it runs in a pipeline. Here it's the `security` GitHub workflow (`.github/workflows/security.yml`): bandit, checkov, Template Analyzer and trivy on every push, every pull request and every Monday, with findings under the repo's Security tab, then Code scanning. It never fails the build. Run it by hand from the Actions tab (security, then Run workflow).

On GitHub, turn on **Dependabot alerts**, **secret scanning** and **code scanning (CodeQL)** under the repository's Settings, then Code security. They're free for public repositories.
