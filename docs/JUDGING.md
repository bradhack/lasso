# Lasso for judges

- **Live app:** https://ca-api-eq6gno2m4qr7w.jollyrock-1439cd71.eastus2.azurecontainerapps.io (best on a phone, or a narrow browser window)
- **Demo video (under 2 minutes):** <!-- VIDEO LINK --> linked from the submission page
- **Category:** Best Multi-Agent System

## Lasso in one minute

Lasso is a free companion app for watching football. While a match plays, it:

1. **Shows each team's chance of winning, live.** A statistical model we call **the Gaffer** recalculates the odds the instant anything happens. Its output is the **Gaffer's Gauge**.
2. **Explains every swing in plain English.** "The red card cost Eastholme 21 points." A team of AI agents writes the story in four languages, for casual fans or for analysts.
3. **Answers your questions.** Type anything ("What were our chances at halftime?") and two AI agents look up the answer from the live data and reply in your language.
4. **Lets you play along.** Predict what happens next against the Gaffer's own odds, for free points called biscuits.

Everything is synthetic, as the rules require: the clubs, players, crests and matches were all made up for this project.

## A two-minute tour

The app replays four matches on a loop, so something is always live. Each match takes about six and a half minutes, and they start a little over a minute apart. The one to watch is **Eastholme Rangers v Brackenford City**: a goal down in the 1st minute, down to ten men in the 5th, level in the 14th, and the winner in the 82nd.

1. Open the link, pick a fan name and a club (choose **Eastholme Rangers** for the full story), then **Fan** or **Analyst**.
2. Open a live match. The **Gaffer's Gauge** shows each side's chances. **Touchline** shows the ball moving on the pitch; switch to **Shots** for every shot of the match.
3. Read **Why it moved**, then tap **AI agents ›**. **Under the hood** shows which AI agents wrote that story, which worked at the same time, the data each one looked up, and how long each took.
4. In **Ask the Gaffer**, tap a suggestion or type your own question, in English, Spanish, Portuguese or French.
5. **Call it:** pick an option and lasso it. You're playing free biscuits against the Gaffer's odds.
6. If your club falls behind, **Touch the sign** to say you still believe. If they draw level, every believer gets a bonus.
   Scroll to **Season outlook** to see what the match means for both clubs' seasons, and tap **Full table** for the league table as it stands. When Eastholme score their winner, they climb from 9th to 5th live.
   In the featured match, watch the 8th minute: VAR checks a goal, and the **VAR check** card shows the chances both ways until the decision. You can call it in **Call it** before it lands.
7. Tap **Listen** under a story or an answer to hear it read aloud. Scroll down to **Match story** for everything said so far. Visit **Stickers** and **Me** for the sticker book, your call history, language and light or dark mode.
8. For TV: add `#/overlay/S5-MD07-03` to the link for a see-through overlay that sits on top of a match broadcast.

## 1. Technical implementation

**In short:** a working, end-to-end live system on Azure, built around a statistical model whose accuracy we measured honestly, on a season it never saw.

- **A whole league to test on.** We wrote a simulator that plays realistic matches event by event: 20 clubs, about 480 players, five seasons, 1,900 matches and 2.2 million events. Each club has hidden "true" strengths, so we can check whether the model finds them. *Where:* `engine/lasso_engine/league.py`, `simulator.py`.
- **The Gaffer, a model that learns and updates.** Before kickoff it rates every team's attack and defense from past results and chances created. During the match it updates the odds with every chance, card and goal, in under a millisecond. *Technically:* a Bayesian hierarchical Poisson model for team strength and Gamma-Poisson live updating. *Where:* `engine/lasso_engine/strength.py`, `inplay.py`.
- **Exact explanations.** Every move of the Gauge is split into its causes (goals, red cards, chances, the clock), and the parts add up exactly to the change. *Technically:* exact Shapley attribution. *Where:* `engine/lasso_engine/explain.py`.
- **A live feed that doesn't break.** Match events stream through Azure Event Hubs to the app's server. If the connection drops, it reconnects. If the server restarts mid-match, it quietly catches up on what it missed. If the stream goes silent, the server keeps the matches playing itself. *Where:* `services/api/lasso_api/feed.py`, `main.py`.
- **Instant updates to every phone,** through Azure Web PubSub. The ball's movements ride along with the once-a-second odds update, so the pitch view costs nothing extra. A push to phones can never hold up a match: it gives up after three seconds, and matches nobody is watching send nothing. *Where:* `services/api/lasso_api/realtime.py`, `matchroom.py`.
- **A whole season, simulated live.** For each match, the rest of the season is played out 10,000 times with the Gaffer's team strengths as of that matchday, drawing the strengths from their uncertainty each time. That gives every club's title, top-four and relegation chances for each possible result of the live match. The phone blends those with the Gauge, so the season odds move every second with no extra realtime traffic, and the table re-sorts as goals go in. *Where:* `engine/lasso_engine/season.py`, `services/api/lasso_api/season.py`, `web/src/components/SeasonOutlook.tsx`.
- **VAR, priced both ways.** When VAR reviews a goal, the Gaffer prices both futures at once (the goal stands, or it's ruled out), opens a quick call on the decision, and settles it when the ruling arrives. A disallowed goal gets its own story with what it would have meant. The Match Feed adds the checks to the synthetic replay with realistic timing. *Where:* `services/api/lasso_api/matchroom.py` (`_var_event`), `feed.py` (`var_plan`), `web/src/components/VarCheck.tsx`.
- **Stories you can hear.** Listen reads stories and answers aloud with Azure AI Speech neural voices, on the same Foundry account and identity (no keys). The server supplies the text, so it can't be used to read anything else, and each clip is made once and cached. Text is rewritten for the ear before it's spoken (minutes, "versus", scores, abbreviations). *Where:* `services/api/lasso_api/speech.py`, `web/src/components/Listen.tsx`.
- **One command to deploy everything.** All the Azure resources are defined as code (Bicep) and deployed with `azd up`. Services sign in to each other with Azure identities, so there are no passwords or keys to leak. *Where:* `infra/`, [deploy guide](DEPLOY.md).
- **Tested on every change.** GitHub Actions runs the model tests, the AI agent workflows (with a scripted stand-in for the AI model), the app build and the infrastructure check on every push. Separate scripts test the live system end to end and play the app in a phone-sized browser. *Where:* `.github/workflows/ci.yml`, `services/api/tests/`, `web/e2e/play.py`.

**How good is the model?** Tested on a full season (380 matches) it never saw. Details in the [model report](model-report.md):

- **Its percentages mean what they say.** When the Gauge says 30%, it happens about 30% of the time. On average it's off by only **1.5 points**.
- **It's close to the best possible.** It gets **85%** of the way from guessing league averages to the forecast you'd make if you knew every team's hidden strength.
- **It finds the hidden truth.** Its team ratings match the true strengths closely: **0.95** for attack and **0.91** for defense, where 1.0 is perfect.
- **It's fast.** The odds and a first version of the story reach phones in **under a second**. The AI agents' richer story follows a few seconds later, so the app never waits on AI.

## 2. Agentic design

**In short:** seven AI agents, each with one job, working in two teams. They get every number from the Gaffer through a shared set of tools, so they explain the math rather than make it up.

They're built with **Microsoft Agent Framework** and run on models in **Microsoft Foundry**. The app's server reaches them through one front door, using the open agent-to-agent protocol (**A2A**). The agents look up live data through tools that the Gaffer offers over the open **Model Context Protocol (MCP)**.

**Team 1: the Match Director** writes a story for every goal, red card, big swing and half. It works in two rounds:

| Round | Agent | Its job | Data it looks up |
|---|---|---|---|
| 1, at the same time | Stats | Finds the numbers that matter | `match_stats`, `recent_events` |
| 1, at the same time | Gaffer | Works out why the chances moved | `why_it_moved`, `gaffers_gauge` |
| 2, at the same time | Narrator | Writes the story in English, Spanish, Portuguese and French | none |
| 2, at the same time | Persona | Writes the fan and analyst versions, a line for each club's supporters, and a halftime team talk | none |
| 2, at the same time | Game Master | Picks the next prediction challenge | `candidate_challenges` |

**Team 2: the Press Room** answers fans' questions. The **Scout** reads the question and decides which data to look up, for example the chances at a given minute or every story so far. The **Gaffer** then writes the answer in the fan's language, using only what the Scout found.

Design choices worth a look:

- **The AI explains; the model decides.** Every percentage, cause and payout comes from the Gaffer. The agents are told never to invent a statistic, and every request carries the true score, minute, chances and key events.
- **The app never waits on AI.** Every story appears instantly from a template, and the agents' version replaces it when ready. Each agent has a time limit, and if one fails, only its own part is skipped.
- **The right amount of thinking.** Short, structured jobs use the model's fastest setting, which cut a story from about 30 seconds to under 15.
- **One shared toolbox.** The Gaffer's ten tools are the only way any agent reaches live data. Any other MCP client, GitHub Copilot for example, can use the same tools.
- **Nothing hidden.** Every agent run records what it looked up, how long it took and how many tokens it used. Fans can see this in the app (**Under the hood**), and it's also sent to Azure Application Insights for monitoring.
- **Measured, not assumed.** An evaluation script replays the showcase match on the live app, asks the agents 25 set questions at set minutes from five test fans (four languages, fan and analyst), and checks every answer and every story automatically against the match's own data. See "How good are the agents?" below.

### How good are the agents?

Every answer and story is checked by code, not by eye: the right language, real percentages and minutes, the correct scorers, red card and halftime chances, that a sent-off player can't be replaced, no invented tactics, staying on topic, ignoring an instruction hidden in a question, neutral wording, no talk of its own machinery, plain words for fans, clean translations (Brazilian Portuguese, no stray English) and length.

| | Passed every check | Typical time | Slowest |
|---|---|---|---|
| Ask the Gaffer answers | **24 of 24** | 7.9 seconds | 10.3 seconds |
| Match stories (each in four languages) | **13 of 13** | 9.6 seconds | 15.6 seconds |

An answer uses about 6,000 tokens across both agents, well under a cent. Full results, with every answer word for word: [agent-eval.md](agent-eval.md). The story figures are from the run before the latest one, because the latest replay ran without agent stories.

**The evaluation made the agents better.** The first run looked fine at a glance but, under strict checks, only 14 of 24 answers passed: English words slipped into translations, the Gaffer invented tactics, answered off-topic questions, and once got a red-card minute wrong. Five runs later, each fix is in the code, not just the instructions: the true events, numbers and rules travel with every question; an off-topic question never reaches the writer; and translations are corrected automatically.

*Where to look:* `services/api/tests/agent_eval.py` (the checks), `services/agents/lasso_agents/director.py` (both teams), `team.py` (the seven agents and their instructions), `server.py` (the A2A front door), `services/api/lasso_api/mcp_tools.py` (the Gaffer's tools).

## 3. Real-world impact

**In short:** Lasso makes a match easier to understand and more fun to follow, for any fan, in their own language, without gambling.

- **A second screen for TV and streaming.** It tells viewers what just changed and why, in one sentence, the moment it happens. The see-through overlay puts the same Gauge on a broadcast.
- **Understanding, not just numbers.** Casual fans get the two biggest reasons for each swing in plain words. Analysts get every cause in points, plus chances created and territory. Ask the Gaffer covers anything else.
- **Built for everyone.** Four languages, two levels of detail, a line for your own club, and light and dark themes. **Listen** reads any story or Gaffer answer aloud in the fan's language with Azure AI Speech neural voices, for fans with low vision or anyone watching the match rather than the phone.
- **Accessible by design.** Both themes pass an automated WCAG 2.2 AA audit (axe-core) on every screen, including color contrast and touch-target size. Sheets work fully by keyboard (focus moves in, Tab stays inside, Escape closes), the page language follows the fan's choice so screen readers use the right voice, live updates are announced politely, and looping animations stop on their own or immediately for anyone who prefers less motion.
- **Fun without gambling.** Biscuits are free points with no cash value and can't be bought, and there's a daily top-up so nobody is locked out. The confidence bonus rewards honesty: your best strategy is always to say what you really believe.
- **Honest numbers.** The Gauge was tested on a season it never saw, and the [model report](model-report.md) shows the results.
- **Cheap to run.** The AI agents only work on matches someone is watching, with daily limits on stories, questions and spoken clips. The whole system costs about $7 to $10 a day with everything switched on.

## 4. User experience and demo

**In short:** a polished phone app with a clear story on every screen and small moments of delight.

- Installs to your phone's home screen like a native app. The Midnight theme (navy and brass) has an Ivory light mode.
- The match page, top to bottom: the score with cards and minutes, the Gaffer's Gauge, the VAR check (during a review), Touch the sign, Touchline, Why it moved (with Listen), Call it, Ask the Gaffer, the match story, stats and the event feed.
- Game features: winning streaks with the **Goldfish** (one missed call a week is forgiven), a 17-sticker book, daily missions, leagues with friends, and your call history.
- When we release an update, open phones pick it up on their own.
- Twenty original club crests, designed as one family (`web/scripts/make_crests.py`).

## 5. Category: Best Multi-Agent System

**In short:** a real team of specialists, not one chatbot.

- **Specialists:** seven agents, each with one job, its own instructions and only the tools it needs.
- **Teamwork:** in the Match Director, agents work at the same time in two rounds, then their work is combined (fan-out and fan-in). In the Press Room, one agent hands its research to the next.
- **A standard way to talk:** the app reaches the agents over A2A, and one front door routes each request to the right team.
- **A shared toolbox:** ten tools over MCP, used by four of the agents. Ask "what does this mean for the table?" and the Scout picks `season_outlook`.
- **Safe and reliable:** each agent has a time limit, there's always a fallback, and a fan's question can't make the agents do anything, because the agent that answers has no tools at all. Daily limits keep costs in check.
- **Visible:** **Under the hood** shows every run in the app, so the multi-agent system is something a fan can actually see.

## How it was built

Brad designed, directed and shipped Lasso, working with two AI assistants:

- **GitHub Copilot** in Agent Mode, with the **Azure MCP Server**, worked against the live Azure resources: deploying, reading logs and fixing infrastructure. It found and fixed an Event Hubs bug from the server logs (commit `f525983`) and a deployment ordering issue in the Bicep files (`4967f0c`). Its guidance for this repo is in `.github/copilot-instructions.md`.
- **Claude** helped with design and much of the code: the synthetic league and the scripts that replay matches into the live feed, the Gaffer model and its evaluation, the agents, the app, the club crests and the submission images.

Every commit records its co-authors.

## Key terms

- **Agent:** an AI model given one job, instructions and, optionally, tools it can use.
- **A2A (Agent2Agent):** an open standard for apps and AI agents to send each other requests.
- **Bayesian model:** a model that keeps track of how sure it is, and updates that as evidence arrives.
- **Calibrated:** a forecast's percentages mean what they say. A calibrated 30% happens about 30% of the time.
- **MCP (Model Context Protocol):** an open standard that lets AI agents use tools, here the Gaffer's live match data.
- **Microsoft Agent Framework:** Microsoft's toolkit for building AI agents and the workflows that connect them.
- **Microsoft Foundry:** Microsoft's platform for hosting and running AI models.
- **Shapley values:** a method from game theory for sharing out credit fairly among causes that act together.
- **Token:** a small piece of text, about three quarters of a word. AI usage and cost are counted in tokens.
- **xG (expected goals):** how likely a shot was to be a goal. A 0.3 xG chance goes in about 3 times in 10.
