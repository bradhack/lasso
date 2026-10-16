# The Gaffer: model report

The Gaffer is the math behind Lasso. It's the model that turns what happens on the pitch into each team's chance of winning, the **Gaffer's Gauge**. This report explains how it works and how well it works, first in plain terms, then in technical detail for anyone who wants to check it. Words in *italics* are explained in the [glossary](#glossary) at the end.

## The short version

- **We built a whole fake league to test it on.** Twenty made-up clubs play five seasons: 1,900 matches and about 2.2 million events (passes, shots, cards). Each club has hidden "true" strengths that the Gaffer never sees, so we can check whether it figures them out.
- **It learns how good each team is.** Before a match, it estimates each side's attacking and defensive strength from past results and chances created. Its estimates line up closely with the hidden truth (0.95 for attack and 0.91 for defense, where 1.0 would be perfect).
- **It updates live, in a fraction of a millisecond.** Every chance, card and goal changes the numbers instantly, so the Gauge on your phone never lags the match.
- **Its percentages mean what they say.** Tested on a season it never saw, when the Gaffer says a team has a 30% chance, that team wins about 30% of the time. On average its percentages are off by only 1.5 points.
- **It's nearly as good as it could be.** It gets 85% of the way from "just guess the league averages" to the best possible forecast, the one you'd make if you knew every team's hidden strength.
- **It explains itself.** Every move of the Gauge is split exactly into its causes, so Lasso can say "the red card cost Eastholme 21 points" rather than just "their chances fell".

## Reproduce everything

All numbers come from `data/model/evaluation.json` and `data/model/mcmc_check.json`:

```bash
cd engine
python -m lasso_engine.generate --out ../data/league --seed 7     # about 2 minutes
python -m lasso_engine.training --data ../data/league --out ../data/model
python -m lasso_engine.evaluate --data ../data/league --model ../data/model --docs ../docs
python -m lasso_engine.mcmc_check --data ../data/league --out ../data/model
cd .. && python docs/charts/render_meter.py
```

## 1. The synthetic league

**In plain terms:** the hackathon requires made-up data, so we wrote a simulator that plays realistic matches, event by event. Because we invented the league, we know the answers: how strong each club really is. That lets us grade the Gaffer properly, which you can't do with real football, where nobody knows a team's "true" strength.

**The details:**

- 20 fictional clubs and about 480 fictional players, over five seasons where every club plays every other home and away: 1,900 matches and about 2.2M events.
- The events are passes (with length, difficulty and ball speed), shots (with *xG*, body part and shot speed), saves, corners, tackles, interceptions, fouls, yellow and red cards, substitutions, and added time.
- Each club has a hidden **true** attack, defense, style and discipline, and these drift between seasons. Each match also has a hidden **form** factor for both teams (a good or bad day), plus a shift at halftime. All of this is written to `truth/`, which the model never reads.
- Matches behave like real ones: a team down a man creates fewer chances, trailing teams push forward and leading teams sit back, and the pace rises late in the game.

The league's averages match a real top-flight league:

| Per match | Lasso league (seasons 1 to 5) | Real top-flight range |
|---|---|---|
| Goals | 2.70 to 2.90 | 2.6 to 2.9 |
| Home win / draw / away win | 41-45% / 25-28% / 28-34% | about 44 / 24 / 32 |
| Shots | 24.9 to 25.5 | about 25 |
| Passes completed | about 84% | 80 to 85% |
| Yellow / red cards | 4.3 / 0.17 | about 4 / 0.1 to 0.15 |

## 2. Before kickoff: how strong is each team?

**In plain terms:** the Gaffer gives every club an attack rating and a defense rating, learned from past matches. It counts chances created (*xG*) as well as goals, because chances are a steadier sign of quality than goals, which involve a lot of luck. Recent matches count for more than old ones. From the two teams' ratings, it works out how many goals each side is likely to score, and so each side's chance of winning. It is *Bayesian*: it keeps track of how sure it is, not just its best guess.

**How well it does**, tested on season 5 (380 matches). It was retrained before every round of matches, using only games already played:

| Forecast | Accuracy score (*RPS*, lower is better) | *Log loss* (lower is better) |
|---|---|---|
| Just use league averages | 0.2256 | 1.077 |
| **The Gaffer** | **0.2025** | **1.014** |
| Perfect knowledge of hidden strengths | 0.1982 | 0.999 |

The Gaffer closes **85% of the gap** between guessing the averages and perfect knowledge. The remaining gap exists because the Gaffer has to learn strengths that the perfect forecast is simply given.

**Does it find the true strengths?** By the end of season 5, its ratings match the hidden truth with a *correlation* of 0.95 for attack and 0.91 for defense. When it says "90% sure the true rating is in this range", it's right for 90% of clubs on attack and all of them on defense.

![Estimated against true team strengths](img/strength_recovery.png)

**The details:** a hierarchical Poisson model, `log λ_home = μ + H + att_home − def_away`, with Normal priors on the attack and defense terms. The likelihood blends goals with xG, and older matches are down-weighted with time decay. The posterior uses a Laplace approximation, which takes milliseconds per refit. We checked that shortcut against the slow, exact method (full MCMC with NUTS, in NumPyro): posterior means correlate at 0.99996, the largest difference in any mean is 0.006, and the median ratio of standard deviations is 1.001. In other words, the shortcut gives the same answer.

## 3. During the match: the live Gauge

**In plain terms:** at kickoff, the Gaffer starts from its pre-match view. As the match goes on, it blends that view with what's actually happening: each chance a team creates nudges up its expected scoring rate, and time running out shrinks how many goals are still to come. It also knows how football changes in different situations. For example, a team down to ten men scores at about 60% of its usual rate. From all of that, it works out the chance of each final result, in under a millisecond, every time something happens.

Those situational effects were learned from seasons 2 to 4, and they come close to the hidden truth:

| Situation | Scoring rate, learned | Hidden truth |
|---|---|---|
| Down a man | 0.62x | 0.68x |
| Up a man | 1.43x | 1.32x |
| Losing | 1.08x | 1.16x |
| Winning | 0.94x | 0.87x |
| After the 75th minute | 1.10x | 1.08x |

The learned "losing" and "winning" effects are smaller than the truth. That's a real-world problem, not a bug: teams that fall behind are often the ones having an off day, so part of the "push when losing" boost is cancelled out by their poor form. Professional sports models face the same issue.

**How well it does on the season it never saw:**

- **Its percentages are honest** (*calibration*). Across every prediction, the gap between what it said and what happened averages **1.5 points**. The chart shows this: the dots sit on the diagonal line, where predicted equals actual.
- **It's good at "will there be another goal?"**, which is what the Call It challenges are priced on. It clearly beats a simpler model that only knows the score and the clock (a *log Bayes factor* of **+33.7**, very strong evidence), and it also beats a version that ignores chances. Most of the gain comes in the second half, once there's enough evidence from the match itself.
- **For the final result**, it matches simpler models (*Brier score* 0.437 against 0.437). The score and the clock carry most of the information about who wins; chances mostly sharpen the short-term "next goal" questions.

![Predicted against actual: the calibration chart](img/reliability.png)

**The details:** each team's scoring rate is Gamma-distributed. The prior comes from the pre-match model, and in-match xG updates it conjugately against time exposure adjusted for game state. The goals still to come follow a Negative Binomial distribution, which gives closed-form win, draw and loss probabilities in microseconds. The game-state multipliers are learned by Poisson regression.

## 4. Explaining every swing

**In plain terms:** when the Gauge moves, Lasso splits the change into four causes: **goals, red cards, chances created and the clock**. It uses a fair-sharing method from game theory (*Shapley values*) that tries each cause with and without the others, so the parts always add up exactly to the total change and nothing is double counted. This is what lets the app and the AI agents say exactly why the chances moved.

Example from the showcase match, Eastholme Rangers 2-1 Brackenford City. Eastholme went down to ten men in the 5th minute, and their chance of winning fell from 46% at kickoff to 10% by the 13th minute:

| Cause | Change |
|---|---|
| Red card | −21 points |
| Goal conceded | −16 points |
| Chances created | +4 points |
| Clock | −2 points |

![The Gaffer's Gauge across the showcase match](img/gaffers_gauge_example.png)

**The details:** exact Shapley values over the four components need 16 model evaluations per explanation. The contributions sum exactly to the total change.

## 5. Call It: fair prices and honest predictions

**In plain terms:** each Call It option pays out according to the Gaffer's own chances, so a 25% option pays about 3.8x your biscuits. There's a small margin so the game isn't trivially beatable, and payouts are kept between 1.05x and 25x. A bonus for stating your confidence is designed so the best strategy is always to say what you really believe.

**The details:** payout multiplier = `floor((1 − 4%) / p, 0.1)`, bounded between 1.05x and 25x. The confidence bonus uses the Brier score, a *proper scoring rule*.

## 6. The season outlook

**In plain terms:** to say what a match means for the season, the Gaffer plays out every remaining fixture 10,000 times, using its team ratings as of that matchday. Counting how often each club finishes first, in the top four or in the bottom three gives its title, top-four and relegation chances. The live match is left out of those simulations and added afterward, so the same simulations answer "what if it ends 2-1?" instantly. Weighting the win, draw and loss answers by the live Gauge gives season odds that move every second.

**The details:** each simulation first draws the team strengths from their Laplace posterior (so the odds include the model's uncertainty about how good each team is), then draws Poisson scores for every remaining fixture. Clubs are ranked by points, goal difference, goals scored, then a random draw. Results of the live match are represented by the nearest final score from the current one (from 1-1, a home win is 2-1). The race shown for each club is the one whose chance differs most between winning and losing, with near ties (within 1.5 points) going to the title, then the top four, then relegation. About a second per match, done once in a worker thread. Tests check that every simulated season has exactly one champion, four top-four clubs and three relegated clubs. *Code:* `engine/lasso_engine/season.py`.

## 7. Player of the Match by impact

**In plain terms:** each player is credited with how much their own actions moved their team's chances, as the Gaffer saw it at that moment. A team's standing is its chance of winning plus half its chance of a draw, so a late equalizer counts as well as a winner. A goal earns the whole swing it caused, and the player who passed to the scorer gets a quarter of it on top. A shot that doesn't go in earns the small lift it gives the Gaffer's view of the team. A save earns the goal it prevented, and a red card counts against the player sent off. The biggest total at full time is the Gaffer's Player of the Match.

**The details:** before each shot or red card, the live state is advanced to the moment of the action, so the change measured is the action's alone, not the clock's. A save's value is `xG × (standing now − standing had the shot gone in)`, computed with the same in-play model. An assist needs a completed pass to the scorer by a teammate within half a minute. Tackles and interceptions don't change the Gaffer's chances directly, so they aren't scored; this is a measure of match-changing actions, not of overall performance. *Code:* `engine/lasso_engine/impact.py`.

## Glossary

- **Bayesian:** a way of modeling that tracks how sure you are, and updates that belief as new evidence arrives.
- **Brier score:** an accuracy score for probability forecasts: the average squared gap between the forecast and what happened. Lower is better.
- **Calibration:** whether forecasts mean what they say. A calibrated 30% happens about 30% of the time.
- **Correlation:** how closely two sets of numbers move together, from 0 (no link) to 1 (a perfect match).
- **Log Bayes factor:** how strongly the evidence favors one model over another. Above about +5 is very strong.
- **Log loss:** an accuracy score that heavily punishes confident forecasts that turn out wrong. Lower is better.
- **MCMC (NUTS):** the slow, exact way to fit a Bayesian model. We used it once to confirm our fast shortcut gives the same answer.
- **Proper scoring rule:** a scoring system where your best strategy is always to report what you truly believe.
- **RPS (ranked probability score):** the standard accuracy score for win, draw or loss forecasts. It gives partial credit for being close (predicting a draw is less wrong than predicting the opposite result). Lower is better.
- **Shapley values:** a method from game theory for sharing out credit fairly among causes that act together.
- **xG (expected goals):** how likely a shot was to be a goal, judged from where and how it was taken. A 0.3 xG chance goes in about 3 times in 10.
