"""Train the Gaffer: pre-match rates, state multipliers and in-play tuning.

    python -m lasso_engine.training --data ../data/league --out ../data/model

Outputs ``gaffer.json`` (all tuned parameters) and ``prematch.parquet``
(pre-match rates and 1X2 probabilities for every match, each computed only
from matches played *before* it, so there is no look-ahead).
"""

from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import nbinom

from .inplay import RELEVANT_EVENTS, Gaffer, InPlayParams, LiveMatch, StateMultipliers
from .strength import StrengthHyper, fit_strength, global_matchday

TRAIN_SEASONS = (2, 3, 4)
TEST_SEASON = 5
GRID_1H = [(1, float(c)) for c in range(0, 46, 5)]
GRID_2H = [(2, float(c)) for c in range(45, 91, 5)]
SNAPSHOT_GRID = GRID_1H + GRID_2H


def load(data: Path) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    matches = pd.read_parquet(data / "matches.parquet")
    events = pd.concat([pd.read_parquet(p, columns=["match_id", "seq", "period", "clock", "team_id",
                                                    "type", "xg", "outcome", "season"])
                        for p in sorted((data / "events").glob("season=*.parquet"))])
    events = events[events.type.isin(RELEVANT_EVENTS)].sort_values(["match_id", "seq"])
    clubs = sorted(pd.read_parquet(data / "clubs.parquet").club_id)
    return matches, events, clubs


def prematch_table(matches: pd.DataFrame, clubs: list[str], hyper: StrengthHyper,
                   seasons: tuple[int, ...]) -> pd.DataFrame:
    rows = []
    for season in seasons:
        for md in range(1, 39):
            post = fit_strength(matches, clubs, int(global_matchday(season, md)), hyper)
            sub = matches[(matches.season == season) & (matches.matchday == md)]
            for r in sub.itertuples():
                eg = post.expected_goals(r.home_id, r.away_id)
                pr = post.outcome_probs(r.home_id, r.away_id, draws=300, seed=hash(r.match_id) % 2**31)
                rows.append({"match_id": r.match_id, "season": season, "matchday": md,
                             "home_id": r.home_id, "away_id": r.away_id,
                             "home_rate": eg["home_rate"], "away_rate": eg["away_rate"],
                             "p_home": pr["home"], "p_draw": pr["draw"], "p_away": pr["away"]})
    return pd.DataFrame(rows)


# --------------------------------------------------------------- multipliers
def segments(events: pd.DataFrame, matches: pd.DataFrame, pre: pd.DataFrame) -> pd.DataFrame:
    """Team-time segments with constant game state, for multiplier regression."""
    info = matches.set_index("match_id")
    rates = pre.set_index("match_id")
    rows = []
    for mid, ev in events.groupby("match_id", sort=False):
        if mid not in rates.index:
            continue
        m = info.loc[mid]
        r = rates.loc[mid]
        teams = (m.home_id, m.away_id)
        a1 = m.added_1h
        goals, reds, xg_acc = [0, 0], [0, 0], [0.0, 0.0]
        seg_start = 0.0

        def close(at: float, late: bool) -> None:
            nonlocal seg_start, xg_acc
            dur = at - seg_start
            if dur > 1e-6:
                for t in (0, 1):
                    o = 1 - t
                    rows.append({"dur": dur, "xg": xg_acc[t],
                                 "rate": (r.home_rate if t == 0 else r.away_rate),
                                 "down": max(0, reds[t] - reds[o]), "up": max(0, reds[o] - reds[t]),
                                 "trail": int(goals[t] < goals[o]), "lead": int(goals[t] > goals[o]),
                                 "late": int(late)})
            seg_start, xg_acc = at, [0.0, 0.0]

        late_closed = False
        for e in ev.itertuples():
            elapsed = e.clock if e.period == 1 else e.clock + a1
            late_now = e.period == 2 and e.clock >= 75
            if late_now and not late_closed:
                close(75 + a1, False)
                late_closed = True
            if e.type in ("half_time", "full_time"):
                continue
            t = 0 if e.team_id == teams[0] else 1
            if e.type == "shot":
                xg_acc[t] += float(e.xg)
                if e.outcome:
                    close(elapsed, late_now)
                    goals[t] += 1
            elif e.type == "red_card":
                close(elapsed, late_now)
                reds[t] += 1
        end = 90 + a1 + m.added_2h
        close(end, True)
    return pd.DataFrame(rows)


def fit_multipliers(seg: pd.DataFrame, total_minutes: float) -> StateMultipliers:
    """Poisson (quasi-likelihood on xG) regression with offset log(rate * duration)."""
    X = seg[["down", "up", "trail", "lead", "late"]].to_numpy(float)
    X = np.column_stack([np.ones(len(X)), X])
    y = seg.xg.to_numpy(float)
    offset = np.log(seg.rate.to_numpy(float) / total_minutes * seg.dur.to_numpy(float))
    beta = np.zeros(X.shape[1])
    for _ in range(50):
        mu = np.exp(X @ beta + offset)
        grad = X.T @ (mu - y)
        H = (X * mu[:, None]).T @ X + 1e-6 * np.eye(len(beta))
        step = np.linalg.solve(H, grad)
        beta -= step
        if np.abs(step).max() < 1e-10:
            break
    e = np.exp(beta)
    return StateMultipliers(down_a_man=float(e[1]), up_a_man=float(e[2]), trailing=float(e[3]),
                            leading=float(e[4]), late_game=float(e[5]))


# ----------------------------------------------------------------- snapshots
def snapshots(events: pd.DataFrame, matches: pd.DataFrame, pre: pd.DataFrame,
              params: InPlayParams) -> pd.DataFrame:
    """Replay each match through LiveMatch, recording state on a time grid."""
    info = matches.set_index("match_id")
    rates = pre.set_index("match_id")
    rows = []
    for mid, ev in events.groupby("match_id", sort=False):
        if mid not in rates.index:
            continue
        m, r = info.loc[mid], rates.loc[mid]
        g = Gaffer(r.home_rate, r.away_rate, params)
        live = LiveMatch(g, m.home_id, m.away_id)
        recs = ev.to_dict("records")
        i = 0
        for period, clock in SNAPSHOT_GRID:
            while i < len(recs) and (recs[i]["period"], recs[i]["clock"]) <= (period, clock) \
                    and recs[i]["type"] != "full_time":
                live.apply(recs[i])
                i += 1
            live.advance(period, clock)
            s = live.state
            row = {"match_id": mid, "period": period, "clock": clock,
                   "home_rate": r.home_rate, "away_rate": r.away_rate,
                   "final_home": m.home_goals, "final_away": m.away_goals}
            for t, side in ((0, "h"), (1, "a")):
                rem, _ = g.remaining_minutes(s)
                row[f"goals_{side}"] = s.goals[t]
                row[f"xg_{side}"] = s.xg[t]
                row[f"exp_{side}"] = s.exposure[t]
                row[f"horizon_{side}"] = rem * g.future_multiplier(s, t)
            rows.append(row)
    return pd.DataFrame(rows)


def tune_inplay(snap: pd.DataFrame, base: InPlayParams) -> tuple[InPlayParams, pd.DataFrame]:
    total = base.expected_total_minutes
    results = []
    for k, w, a in itertools.product([4, 8, 12, 16, 24, 32, 64], [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0], [0.0, 0.15, 0.3]):
        ll = 0.0
        for side in ("h", "a"):
            r0 = snap[f"{'home' if side == 'h' else 'away'}_rate"] / total
            ev = a * snap[f"goals_{side}"] + (1 - a) * snap[f"xg_{side}"]
            shape = k + w * ev
            rate = k / r0 + w * snap[f"exp_{side}"]
            rem_goals = snap[f"final_{'home' if side == 'h' else 'away'}"] - snap[f"goals_{side}"]
            ll += nbinom.logpmf(rem_goals, shape, rate / (rate + snap[f"horizon_{side}"])).sum()
        results.append({"prior_shape": k, "evidence_weight": w, "alpha_goals": a, "loglik": ll})
    res = pd.DataFrame(results).sort_values("loglik", ascending=False)
    best = res.iloc[0]

    # Refine the grid optimum with a bounded continuous search.
    def nll(v: np.ndarray) -> float:
        k, w, a = np.exp(v[0]), np.exp(v[1]), v[2]
        ll = 0.0
        for side, name in (("h", "home"), ("a", "away")):
            r0 = snap[f"{name}_rate"] / total
            shape = k + w * (a * snap[f"goals_{side}"] + (1 - a) * snap[f"xg_{side}"])
            rate = k / r0 + w * snap[f"exp_{side}"]
            rem_goals = snap[f"final_{name}"] - snap[f"goals_{side}"]
            ll += nbinom.logpmf(rem_goals, shape, rate / (rate + snap[f"horizon_{side}"])).sum()
        return -float(ll)

    x0 = np.array([np.log(best.prior_shape), np.log(best.evidence_weight), best.alpha_goals])
    opt = minimize(nll, x0, method="L-BFGS-B",
                   bounds=[(np.log(1), np.log(500)), (np.log(0.1), np.log(50)), (0.0, 1.0)])
    k, w, a = float(np.exp(opt.x[0])), float(np.exp(opt.x[1])), float(opt.x[2])
    res = pd.concat([pd.DataFrame([{"prior_shape": k, "evidence_weight": w, "alpha_goals": a,
                                    "loglik": -opt.fun, "refined": True}]), res], ignore_index=True)
    tuned = InPlayParams(prior_shape=k, evidence_weight=w,
                         alpha_goals=a, multipliers=base.multipliers,
                         added_1h=base.added_1h, added_2h=base.added_2h)
    return tuned, res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="../data/league")
    ap.add_argument("--out", default="../data/model")
    args = ap.parse_args()
    data, out = Path(args.data), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    matches, events, clubs = load(data)
    hyper = StrengthHyper()

    print("pre-match rates (rolling, no look-ahead)...")
    pre = prematch_table(matches, clubs, hyper, TRAIN_SEASONS + (TEST_SEASON,))
    pre.to_parquet(out / "prematch.parquet", index=False)

    train_m = matches[matches.season.isin(TRAIN_SEASONS)]
    train_ev = events[events.season.isin(TRAIN_SEASONS)]
    added = InPlayParams(added_1h=tuple(train_m.added_1h.astype(float)),
                         added_2h=tuple(train_m.added_2h.astype(float)))

    print("learning game-state multipliers...")
    seg = segments(train_ev, train_m, pre)
    mult = fit_multipliers(seg, added.expected_total_minutes)
    print("  ", mult)
    base = InPlayParams(multipliers=mult, added_1h=added.added_1h, added_2h=added.added_2h)

    print("replaying training matches and tuning the Gaffer...")
    snap = snapshots(train_ev, train_m, pre, base)
    tuned, grid = tune_inplay(snap, base)
    print(grid.head(5).to_string())

    model = {
        "version": 1,
        "train_seasons": list(TRAIN_SEASONS),
        "strength_hyper": asdict(hyper),
        "inplay": tuned.to_dict(),
    }
    (out / "gaffer.json").write_text(json.dumps(model, indent=2))
    grid.to_csv(out / "inplay_tuning.csv", index=False)
    print("wrote", out / "gaffer.json")


if __name__ == "__main__":
    main()
