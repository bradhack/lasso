# Lasso: Believe Your Call

**See why the odds moved. Then out-predict the AI Gaffer on what's next.**

Lasso is a live, multi-agent match companion for the Microsoft and Premier League *Inside the Game* hackathon. It ingests synthetic football events, explains every swing in each team's chance of winning (the **Believe-o-Meter**) in plain language, and invites fans to make free-to-play calls against **the Gaffer**, a Bayesian live match model.

## Repository layout

| Path | What it is |
|---|---|
| `engine/` | Python package `lasso_engine`: synthetic league, event simulator, the Gaffer (Bayesian models), Shapley explanations, Call It markets, evaluation |
| `data/model/` | Trained parameters (`gaffer.json`), rolling pre-match forecasts and evaluation results |
| `data/league/` | Generated league (git-ignored; deterministic, regenerate in about 2 minutes) |
| `docs/` | [Model report](docs/model-report.md) and charts |
| `agents/` | Microsoft Agent Framework agents (in progress) |
| `web/` | React + TypeScript mobile app (in progress) |
| `infra/` | Bicep + azd infrastructure (in progress) |

## Quick start

```bash
cd engine
pip install -e ".[dev,mcmc]"
python -m lasso_engine.generate --out ../data/league --seed 7
python -m lasso_engine.training --data ../data/league --out ../data/model
python -m lasso_engine.evaluate --data ../data/league --model ../data/model --docs ../docs
pytest
```

## Data

All data is synthetic, as the hackathon rules require. Clubs, players and matches are invented, and no real league data is used. The generator is tuned to published league-wide averages, such as goals per match, home advantage and shot volume.
