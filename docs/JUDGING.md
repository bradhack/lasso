# Lasso for judges

- **Live app:** https://ca-api-eq6gno2m4qr7w.jollyrock-1439cd71.eastus2.azurecontainerapps.io (built for phones; on a desktop browser the match page spreads into two columns, with Play and Standings & stats as tabs beside the match)
- **Demo video (under 2 minutes):** <!-- VIDEO LINK --> linked from the submission page
- **Short on time? Jump straight to a moment** in your own private replay of the showcase match (pick a fan name first, then it starts):
  - [The VAR check (8')](https://ca-api-eq6gno2m4qr7w.jollyrock-1439cd71.eastus2.azurecontainerapps.io/#/replay/S5-MD07-03/6): VAR reviews a goal, and the Gauge shows the chances both ways until the decision
  - [The equalizer (14')](https://ca-api-eq6gno2m4qr7w.jollyrock-1439cd71.eastus2.azurecontainerapps.io/#/replay/S5-MD07-03/12.5): ten men, a goal down, and level
  - [The winner (82')](https://ca-api-eq6gno2m4qr7w.jollyrock-1439cd71.eastus2.azurecontainerapps.io/#/replay/S5-MD07-03/83): a VAR check, the winner, the climb up the table and the Player of the Match vote
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

You don't have to wait for the loop. **Watch the big moments**, at the top of the match list and under every match's Gauge, lists each goal, red card and VAR check; pick one and your own private replay starts just before it. Everything works in it as it does during a match (the agents, Ask the Gaffer, VAR, the table, the vote), and nobody else's match changes.

1. Open the link, pick a fan name and a club (choose **Eastholme Rangers** for the full story), then **Fan** or **Analyst**.
2. Open a live match. The score and the **Gaffer's Gauge** stay on top; below them, three tabs: **Live**, **Play** and **Standings & stats**. On a phone, a slim scoreboard pins to the top as you scroll. Goals and VAR decisions flash up as a banner as they happen.
3. **Live:** read **Why it moved**, then tap **AI agents ›**. **Under the hood** shows which AI agents wrote that story, which worked at the same time, the data each one looked up, and how long each took. **Touchline** shows the ball moving on the pitch (switch to **Shots** for every shot, or **Goals** to pick a goal and see **How it was built**, the numbered passing move behind it), and the **Match story** keeps every story with an icon for each kind of moment; switch it to **All events** for every chance, card, substitution and VAR check in between.
4. **Ask & play** (or tap **Ask the Gaffer ›** under Why it moved): **Ask the Gaffer** (tap a suggestion or type your own question in English, Spanish, Portuguese or French; follow-ups like "who's his sub?" work), **Call it** (pick an option and lasso it; free biscuits against the Gaffer's odds) and **Player of the Match**, ranked by how much each player's own actions moved the chances. Vote from halftime; match the Gaffer's pick at full time for a bonus. A dot on the tab means there's something to do.
5. **Standings & stats:** **Season outlook** shows what the match means for both clubs' seasons (tap **Full standings** for the standings as they are now; when Eastholme score their winner they climb from 9th to 5th live), and the analyst stats show who leads each stat and by how much.
6. If your club falls behind, **Touch the sign** to say you still believe. If they draw level, every believer gets a bonus. In the featured match, watch the 8th minute: VAR checks a goal, the **VAR check** card shows the chances both ways, and you can call the decision in **Play** before it lands.
7. Tap **Listen** on a story, an answer or any event in the timeline (switch it to **All events**) to hear it read aloud. Scroll down to **Match story** for everything said so far. Visit **Stickers** and **Me** for the sticker book, your call history, language and light or dark mode.
8. For TV: add `#/overlay/S5-MD07-03` to the link for a see-through overlay that sits on top of a match broadcast.

## 1. Technical implementation

**In short:** a working, end-to-end live system on Azure, built around a statistical model whose accuracy we measured honestly, on a season it never saw.

- **A whole league to test on.** We wrote a simulator that plays realistic matches event by event: 20 clubs, about 480 players, five seasons, 1,900 matches and 2.2 million events. Each club has hidden "true" strengths, so we can check whether the model finds them. *Where:* `engine/lasso_engine/league.py`, `simulator.py`.
- **The Gaffer, a model that learns and updates.** Before kickoff it rates every team's attack and defense from past results and chances created. During the match it updates the odds with every chance, card and goal, in under a millisecond. *Technically:* a Bayesian hierarchical Poisson model for team strength and Gamma-Poisson live updating. *Where:* `engine/lasso_engine/strength.py`, `inplay.py`.
- **Exact explanations.** Every move of the Gauge is split into its causes (goals, red cards, chances, the clock), and the parts add up exactly to the change. *Technically:* exact Shapley attribution. *Where:* `engine/lasso_engine/explain.py`.
- **A live feed that doesn't break.** Match events stream through Azure Event Hubs to the app's server. If the connection drops, it reconnects. If the server restarts mid-match, it quietly catches up on what it missed. If the stream goes silent, the server keeps the matches playing itself. *Where:* `services/api/lasso_api/feed.py`, `main.py`.
- **Instant updates to every phone,** through Azure Web PubSub. The ball's movements ride along with the once-a-second odds update, so the pitch view costs nothing extra. A push to phones can never hold up a match: it gives up after three seconds, and matches nobody is watching send nothing. *Where:* `services/api/lasso_api/realtime.py`, `matchroom.py`.
- **A whole season, simulated live.** For each match, the rest of the season is played out 10,000 times with the Gaffer's team strengths as of that matchday, drawing the strengths from their uncertainty each time. That gives every club's title, top-four and relegation chances for each possible result of the live match. The phone blends those with the Gauge, so the season odds move every second with no extra realtime traffic, and the table re-sorts as goals go in. *Where:* `engine/lasso_engine/season.py`, `services/api/lasso_api/season.py`, `web/src/components/SeasonOutlook.tsx`.
- **Player of the Match, measured.** Every goal, chance, save and red card is valued by the Gaffer at the instant it happens: how much it moved the team's chance of winning plus half its chance of a draw. The assist gets a quarter of the goal, and a save earns the goal it prevented (the swing a goal would have caused, times the shot's xG). The clock is moved to the moment of the action first, so time running down is never credited to anyone. *Where:* `engine/lasso_engine/impact.py`, `services/api/lasso_api/matchroom.py` (`_impact`), `web/src/components/PlayerOfMatch.tsx`.
- **Private replays for anyone who drops in.** Watch the big moments starts a private copy of a match from any minute: the earlier minutes are caught up silently (no stories or agent runs for minutes nobody watched), then the match plays on live for that one fan, with its own calls, questions and vote. Private replays never appear in the match list or the agents' match list, end when the fan starts another, and close 15 minutes after full time. *Where:* `services/api/lasso_api/main.py` (`private_replay`), `feed.py` (`replay`, `big_moments`), `web/src/components/BigMoments.tsx`.
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
- **One shared toolbox.** The Gaffer's eleven tools are the only way any agent reaches live data. Any other MCP client, GitHub Copilot for example, can use the same tools.
- **Nothing hidden.** Every agent run records what it looked up, how long it took and how many tokens it used. Fans can see this in the app (**Under the hood**), and it's also sent to Azure Application Insights for monitoring.
- **Measured, not assumed.** An evaluation script replays the showcase match on the live app, asks the agents 27 set questions at set minutes (including a follow-up that only makes sense with the question before it) from five test fans (four languages, fan and analyst), and checks every answer and every story automatically against the match's own data. See "How good are the agents?" below.

### How good are the agents?

Every answer and story is checked by code, not by eye: the right language, real percentages and minutes, each percentage belonging to the team it's given to, no real club names, the correct scorers, red card and halftime chances, that a sent-off player can't be replaced, no invented tactics, staying on topic, ignoring an instruction hidden in a question, neutral wording, no talk of its own machinery, plain words for fans, clean translations (Brazilian Portuguese, no stray English) and length.

| | Passed every check | Typical time | Slowest |
|---|---|---|---|
| Ask the Gaffer answers | **26 of 26** | 7.8 seconds | 22.3 seconds |
| Match stories (each in four languages) | **12 of 12** | 11.9 seconds | 14.9 seconds |

Both numbers come from the same run, on the live app, with every feature in place: the first run where every answer and every story passed every check. The checks get stricter after each run, so each is held to more than the last. Recent runs added checks for the draw's chance, the scorer's name, numerals for minutes, real club names, percentages given to the right team, next-goal chances, who leads and when goals happened, and headlines that agree with the numbers. Reading every line anyway still turns up things no check covered yet. This time it was a story saying Brackenford went "ahead 0-1" and another with "nine minutes left" at 89'. The app now puts the leader's score first, the story writer is told the minutes left, and both have checks. An answer uses about 7,000 tokens across both agents, well under a cent. Full results, with every answer word for word: [agent-eval.md](agent-eval.md).

**The evaluation made the agents better.** The first run looked fine at a glance but, under strict checks, only 14 of 24 answers passed: English words slipped into translations, the Gaffer invented tactics, answered off-topic questions, and once got a red-card minute wrong. Run after run, each fix went into the code, not just the instructions: the true events, numbers and rules travel with every question; an off-topic question never reaches the writer; translations are corrected automatically; a reply with broken formatting is recovered rather than lost; and after full time the Gaffer talks about the result, never "a 100% chance".

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
- The match page: the score with cards and minutes and the Gaffer's Gauge always in view, the VAR check and Touch the sign when they apply, then three tabs. **Live:** Why it moved (with Listen), Touchline and the match story (one timeline with an icon for each moment, and every event on request). **Ask & play:** Ask the Gaffer, Call it and Player of the Match. **Standings & stats:** Season outlook and the analyst stats. Goals and VAR decisions arrive as a banner too.
- Game features: winning streaks with the **Goldfish** (one missed call a week is forgiven), a 23-sticker book (with stickers for Ask the Gaffer, Listen, VAR calls, Player of the Match picks and climbing the table), daily missions, leagues with friends, and your call history.
- When we release an update, open phones pick it up on their own.
- Twenty original club crests, designed as one family (`web/scripts/make_crests.py`).

## 5. Category: Best Multi-Agent System

**In short:** a real team of specialists, not one chatbot.

- **Specialists:** seven agents, each with one job, its own instructions and only the tools it needs.
- **Teamwork:** in the Match Director, agents work at the same time in two rounds, then their work is combined (fan-out and fan-in). In the Press Room, one agent hands its research to the next.
- **A standard way to talk:** the app reaches the agents over A2A, and one front door routes each request to the right team.
- **A shared toolbox:** eleven tools over MCP, used by four of the agents. Ask "how would this result change the standings?" and the Scout picks `season_outlook`; ask who's playing best and it picks `player_impact`.
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
