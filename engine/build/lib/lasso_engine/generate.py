"""Generate the full synthetic league history to Parquet.

Usage::

    python -m lasso_engine.generate --out ../data/league --seed 7

Output layout (``truth/`` is for evaluation only; models must never read it)::

    clubs.parquet
    players.parquet            one row per player per season
    matches.parquet            results, xG, shots, red cards
    events/season=N.parquet    every match event
    truth/club_truth.parquet   hidden generative strengths
    truth/config.json          generative constants
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from .league import League, build_league, double_round_robin
from .simulator import MatchSimulator


def _simulate_season(args: tuple[int, int, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    seed, season, out = args
    league = build_league(seed)
    rng = np.random.default_rng([seed, season])
    sim = MatchSimulator(league, rng)
    fixtures = double_round_robin([c.club_id for c in league.clubs], rng)
    rows, event_rows = [], []
    for md, pairs in enumerate(fixtures, start=1):
        for i, (h, a) in enumerate(pairs):
            mid = f"S{season}-MD{md:02d}-{i:02d}"
            res = sim.simulate(mid, season, md, h, a)
            r = asdict(res)
            r.pop("events")
            rows.append(r)
            event_rows.extend(e.to_dict() for e in res.events)
    matches = pd.DataFrame(rows)
    events = pd.DataFrame(event_rows)
    events["season"] = season
    ev_dir = Path(out) / "events"
    ev_dir.mkdir(parents=True, exist_ok=True)
    events.to_parquet(ev_dir / f"season={season}.parquet", index=False)
    return matches, events.groupby("type").size().rename(season).to_frame()


def write_league(league: League, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "truth").mkdir(exist_ok=True)
    pd.DataFrame([asdict(c) for c in league.clubs]).to_parquet(out / "clubs.parquet", index=False)
    players = []
    for season, squads in league.squads.items():
        for cid, squad in squads.items():
            for p in squad:
                d = asdict(p)
                # Hidden skill attributes go to truth, not the public player table.
                players.append({k: d[k] for k in ("player_id", "club_id", "name", "position", "shirt")}
                               | {"season": season})
    pd.DataFrame(players).to_parquet(out / "players.parquet", index=False)
    truth = [asdict(t) for s in league.truth.values() for t in s.values()]
    pd.DataFrame(truth).to_parquet(out / "truth" / "club_truth.parquet", index=False)
    (out / "truth" / "config.json").write_text(json.dumps(asdict(league.config), indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="../data/league")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()
    out = Path(args.out)
    league = build_league(args.seed)
    write_league(league, out)
    jobs = [(args.seed, s, str(out)) for s in range(1, league.config.n_seasons + 1)]
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(_simulate_season, jobs))
    matches = pd.concat([m for m, _ in results], ignore_index=True)
    hidden = ["home_form", "away_form"]
    matches[["match_id", *hidden]].to_parquet(out / "truth" / "match_truth.parquet", index=False)
    matches = matches.drop(columns=hidden)
    matches.to_parquet(out / "matches.parquet", index=False)
    counts = pd.concat([c for _, c in results], axis=1).fillna(0).astype(int)
    print(counts.to_string())
    print(summarise(matches).to_string())


def summarise(matches: pd.DataFrame) -> pd.DataFrame:
    g = matches.groupby("season")
    return pd.DataFrame({
        "matches": g.size(),
        "goals_pm": g.apply(lambda d: (d.home_goals + d.away_goals).mean()),
        "home_win": g.apply(lambda d: (d.home_goals > d.away_goals).mean()),
        "draw": g.apply(lambda d: (d.home_goals == d.away_goals).mean()),
        "away_win": g.apply(lambda d: (d.home_goals < d.away_goals).mean()),
        "xg_pm": g.apply(lambda d: (d.home_xg + d.away_xg).mean()),
        "shots_pm": g.apply(lambda d: (d.home_shots + d.away_shots).mean()),
        "reds_pm": g.apply(lambda d: (d.home_red + d.away_red).mean()),
    }).round(3)


if __name__ == "__main__":
    main()
