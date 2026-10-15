"""Evaluate the Gaffer on the held-out season against the hidden truth.

    python -m lasso_engine.evaluate --data ../data/league --model ../data/model --docs ../docs

Because we built the universe, we know every club's true strength and every
match's hidden form, so we can measure not just accuracy but how close the
model gets to the best possible forecast.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import nbinom, poisson  # noqa: E402

from .inplay import Gaffer, InPlayParams, LiveMatch, StateMultipliers  # noqa: E402
from .metrics import brier, log_loss, outcome_index, reliability, rps  # noqa: E402
from .strength import StrengthHyper, fit_strength, global_matchday  # noqa: E402
from .training import SNAPSHOT_GRID, TEST_SEASON, TRAIN_SEASONS, load, snapshots  # noqa: E402

DEMO_MATCH = "S5-MD07-03"  # ten-man comeback, deterministic with seed 7

# Validated categorical palette (dataviz validator: light surface, all checks pass).
PLUM, GOLD, BLUE = "#8A3FA0", "#B8862F", "#2F7DC4"
INK, MUTED, GRID, SURFACE = "#1F1A24", "#6B6470", "#E6E2E8", "#FCFCFB"


def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def oracle_prematch(matches: pd.DataFrame, truth: pd.DataFrame, cfg: dict, form_sd: float,
                    draws: int = 400, seed: int = 0) -> np.ndarray:
    """Best achievable pre-match forecast: true strengths, integrating unknown match form."""
    rng = np.random.default_rng(seed)
    t = truth.set_index(["season", "club_id"])
    g = np.arange(13)
    out = []
    for r in matches.itertuples():
        th, ta = t.loc[(r.season, r.home_id)], t.loc[(r.season, r.away_id)]
        lh = np.exp(cfg["base_log_rate"] + cfg["home_advantage"] + th.attack - ta.defense)
        la = np.exp(cfg["base_log_rate"] + ta.attack - th.defense)
        f = rng.normal(0, form_sd, size=(draws, 2))
        ph = poisson.pmf(g[None, :], lh * np.exp(f[:, :1])).mean(0)
        pa = poisson.pmf(g[None, :], la * np.exp(f[:, 1:])).mean(0)
        j = np.outer(ph, pa)
        out.append([np.tril(j, -1).sum(), np.trace(j), np.triu(j, 1).sum()])
    return np.array(out)


def believe_o_meter_path(match_id: str, events: pd.DataFrame, matches: pd.DataFrame,
                         pre: pd.DataFrame, params: InPlayParams,
                         club_short: dict | None = None) -> pd.DataFrame:
    """Minute-by-minute and event-by-event probabilities for one match."""
    m = matches.set_index("match_id").loc[match_id]
    r = pre.set_index("match_id").loc[match_id]
    live = LiveMatch(Gaffer(r.home_rate, r.away_rate, params), m.home_id, m.away_id)
    recs = events[events.match_id == match_id].sort_values("seq").to_dict("records")
    rows = []
    names_short = {"home": m.home_id, "away": m.away_id}
    if club_short is not None:
        names_short = {"home": club_short[m.home_id], "away": club_short[m.away_id]}

    def snap(note: str = "") -> None:
        p = live.probabilities()
        rows.append({"elapsed": live.state.elapsed, "home": p["home"], "draw": p["draw"],
                     "away": p["away"], "note": note})

    snap()
    i = 0
    for period, end in ((1, 45 + m.added_1h), (2, 90 + m.added_2h)):
        clock = 0.0 if period == 1 else 45.0
        while clock <= end:
            while i < len(recs) and (recs[i]["period"], recs[i]["clock"]) <= (period, clock):
                e = recs[i]
                live.apply(e)
                i += 1
                team = "home" if e["team_id"] == m.home_id else "away"
                if e["type"] == "shot" and e["outcome"]:
                    snap(f"Goal ({names_short[team]}) {int(e['clock'])}'")
                elif e["type"] == "red_card":
                    snap(f"Red ({names_short[team]}) {int(e['clock'])}'")
            live.advance(period, clock)
            snap()
            clock += 1.0
    while i < len(recs):
        live.apply(recs[i])
        i += 1
    snap()
    return pd.DataFrame(rows)


def inplay_paths(events: pd.DataFrame, matches: pd.DataFrame, pre: pd.DataFrame,
                 variants: dict[str, InPlayParams]) -> pd.DataFrame:
    info, rates = matches.set_index("match_id"), pre.set_index("match_id")
    rows = []
    for mid, ev in events.groupby("match_id", sort=False):
        m, r = info.loc[mid], rates.loc[mid]
        recs = ev.to_dict("records")
        idx = outcome_index(m.home_goals, m.away_goals).item()
        for name, params in variants.items():
            live = LiveMatch(Gaffer(r.home_rate, r.away_rate, params), m.home_id, m.away_id)
            i = 0
            for k, (period, clock) in enumerate(SNAPSHOT_GRID):
                while i < len(recs) and (recs[i]["period"], recs[i]["clock"]) <= (period, clock) \
                        and recs[i]["type"] != "full_time":
                    live.apply(recs[i])
                    i += 1
                live.advance(period, clock)
                p = live.probabilities()
                minute = clock if period == 1 else clock
                rows.append({"match_id": mid, "variant": name, "step": k, "period": period,
                             "minute": minute, "p_home": p["home"], "p_draw": p["draw"],
                             "p_away": p["away"], "outcome": idx})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="../data/league")
    ap.add_argument("--model", default="../data/model")
    ap.add_argument("--docs", default="../docs")
    args = ap.parse_args()
    data, model_dir, docs = Path(args.data), Path(args.model), Path(args.docs)
    img = docs / "img"
    img.mkdir(parents=True, exist_ok=True)

    matches, events, clubs = load(data)
    model = json.loads((model_dir / "gaffer.json").read_text())
    params = InPlayParams.from_dict(model["inplay"])
    hyper = StrengthHyper(**{k: tuple(v) if isinstance(v, list) else v
                             for k, v in model["strength_hyper"].items()})
    pre = pd.read_parquet(model_dir / "prematch.parquet")
    truth = pd.read_parquet(data / "truth" / "club_truth.parquet")
    cfg = json.loads((data / "truth" / "config.json").read_text())

    test = matches[matches.season == TEST_SEASON].sort_values(["matchday", "match_id"])
    tpre = pre.set_index("match_id").loc[test.match_id]
    y = outcome_index(test.home_goals, test.away_goals)
    results: dict = {"test_season": TEST_SEASON, "train_seasons": list(TRAIN_SEASONS),
                     "n_test_matches": int(len(test))}

    # ---------------------------------------------------------- pre-match
    train = matches[matches.season.isin(TRAIN_SEASONS)]
    ti = outcome_index(train.home_goals, train.away_goals)
    base = np.bincount(ti, minlength=3) / len(ti)
    P_base = np.tile(base, (len(test), 1))
    P_gaffer = tpre[["p_home", "p_draw", "p_away"]].to_numpy()
    P_oracle = oracle_prematch(test, truth, cfg, cfg["match_form_sd"])
    pm = {}
    for name, P in (("Base rates", P_base), ("Gaffer", P_gaffer), ("Oracle (true strengths)", P_oracle)):
        pm[name] = {"rps": rps(P, y), "brier": brier(P, y), "log_loss": log_loss(P, y)}
    gap = pm["Base rates"]["rps"] - pm["Oracle (true strengths)"]["rps"]
    pm["Gaffer"]["share_of_achievable_gain"] = (pm["Base rates"]["rps"] - pm["Gaffer"]["rps"]) / gap
    results["prematch"] = pm

    # ---------------------------------------------------------- in-play
    ident = StateMultipliers(1, 1, 1, 1, 1)
    variants = {
        "Gaffer": params,
        "Score, clock & cards": replace(params, evidence_weight=0.0),
        "Score & clock only": replace(params, evidence_weight=0.0, multipliers=ident),
    }
    test_ev = events[events.season == TEST_SEASON]
    paths = inplay_paths(test_ev, test, pre, variants)
    by_step = []
    for (name, step), d in paths.groupby(["variant", "step"]):
        P = d[["p_home", "p_draw", "p_away"]].to_numpy()
        by_step.append({"variant": name, "step": step, "period": d.period.iloc[0],
                        "minute": d.minute.iloc[0], "brier": brier(P, d.outcome.to_numpy()),
                        "rps": rps(P, d.outcome.to_numpy()), "log_loss": log_loss(P, d.outcome.to_numpy())})
    by_step = pd.DataFrame(by_step)
    overall = {}
    for name, d in paths.groupby("variant"):
        P = d[["p_home", "p_draw", "p_away"]].to_numpy()
        overall[name] = {"brier": brier(P, d.outcome.to_numpy()), "rps": rps(P, d.outcome.to_numpy()),
                         "log_loss": log_loss(P, d.outcome.to_numpy())}
    results["inplay_overall"] = overall
    g = paths[paths.variant == "Gaffer"]
    # One-vs-rest reliability pooled over the three outcomes, excluding settled (0/1) states.
    p_all = np.concatenate([g.p_home, g.p_draw, g.p_away])
    y_all = np.concatenate([(g.outcome == 0), (g.outcome == 1), (g.outcome == 2)]).astype(float)
    live_mask = (p_all > 0.005) & (p_all < 0.995)
    rel = reliability(p_all[live_mask], y_all[live_mask], bins=10)
    results["reliability"] = rel
    results["calibration_error"] = float(sum(b["n"] * abs(b["pred"] - b["obs"]) for b in rel) /
                                         sum(b["n"] for b in rel))

    # ---------------------------------------------------------- recovery
    post = fit_strength(matches, clubs, int(global_matchday(TEST_SEASON, 38)) + 1, hyper)
    t5 = truth[truth.season == TEST_SEASON].set_index("club_id").loc[clubs]
    sd = post.sd()
    n = len(clubs)
    att_m, def_m = post.attack().to_numpy(), post.defense().to_numpy()
    att_sd, def_sd = sd[2:2 + n], sd[2 + n:]
    cover = lambda m, s, t: float(np.mean(np.abs(m - t) <= 1.645 * s))  # noqa: E731
    results["strength_recovery"] = {
        "attack_corr": float(np.corrcoef(att_m, t5.attack)[0, 1]),
        "defense_corr": float(np.corrcoef(def_m, t5.defense)[0, 1]),
        "attack_90ci_coverage": cover(att_m, att_sd, t5.attack.to_numpy()),
        "defense_90ci_coverage": cover(def_m, def_sd, t5.defense.to_numpy()),
        "home_advantage": {"posterior": post.home, "truth": cfg["home_advantage"]},
    }
    results["multipliers"] = {
        "learned": model["inplay"]["multipliers"],
        "truth": {k: cfg[k] for k in ("down_a_man", "up_a_man", "trailing", "leading", "late_game")},
    }
    (model_dir / "evaluation.json").write_text(json.dumps(results, indent=2))

    # ---------------------------------------------------------- charts
    # Held-out likelihood of goals still to come (what the micro-markets price).
    total = params.expected_total_minutes
    goal_ll = {}
    for name, vp in variants.items():
        snap = snapshots(test_ev, test, pre, vp)
        ll = 0.0
        for side, nm in (("h", "home"), ("a", "away")):
            r0 = snap[f"{nm}_rate"] / total
            ev_ = vp.alpha_goals * snap[f"goals_{side}"] + (1 - vp.alpha_goals) * snap[f"xg_{side}"]
            shape = vp.prior_shape + vp.evidence_weight * ev_
            rate = vp.prior_shape / r0 + vp.evidence_weight * snap[f"exp_{side}"]
            rem = snap[f"final_{nm}"] - snap[f"goals_{side}"]
            ll += float(nbinom.logpmf(rem, shape, rate / (rate + snap[f"horizon_{side}"])).sum())
        goal_ll[name] = ll
    results["remaining_goals_loglik"] = goal_ll
    results["log_bayes_factor_vs_naive"] = goal_ll["Gaffer"] - goal_ll["Score & clock only"]

    # Believe-o-Meter trajectory for the showcase match.
    club_tbl = pd.read_parquet(data / "clubs.parquet").set_index("club_id")
    traj = believe_o_meter_path(DEMO_MATCH, test_ev, test, pre, params, club_tbl["short"].to_dict())
    traj.to_json(model_dir / "demo_trajectory.json", orient="records")
    # The showcase chart itself is drawn by docs/charts/render_meter.py from this JSON.

    fig, ax = plt.subplots(figsize=(4.6, 4.6), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    _style(ax)
    ax.plot([0, 1], [0, 1], color=MUTED, linewidth=1, linestyle="--")
    ax.plot([b["pred"] for b in rel], [b["obs"] for b in rel], color=PLUM, linewidth=2,
            marker="o", markersize=6, markeredgecolor=SURFACE, markeredgewidth=2)
    ax.text(0.62, 0.25, "Perfect calibration", color=MUTED, fontsize=8.5, rotation=45)
    ax.set_xlabel("Gaffer's live probability", color=MUTED, fontsize=9)
    ax.set_ylabel("How often it happened", color=MUTED, fontsize=9)
    ax.set_title("Believe-o-Meter calibration", color=INK, fontsize=11, loc="left")
    fig.tight_layout()
    fig.savefig(img / "reliability.png", facecolor=SURFACE)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(8, 4), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    for ax, est, err, tr, label in ((axes[0], att_m, att_sd, t5.attack.to_numpy(), "Attack"),
                                    (axes[1], def_m, def_sd, t5.defense.to_numpy(), "Defense")):
        _style(ax)
        lim = max(np.abs(np.r_[est, tr]).max() * 1.15, 0.1)
        ax.plot([-lim, lim], [-lim, lim], color=MUTED, linewidth=1, linestyle="--")
        ax.errorbar(tr, est, yerr=1.645 * err, fmt="o", color=PLUM, ecolor="#C9A6D4",
                    elinewidth=1.5, markersize=6, markeredgecolor=SURFACE, markeredgewidth=1.5)
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)
        ax.set_xlabel(f"True {label.lower()} (hidden)", color=MUTED, fontsize=9)
        ax.set_ylabel("Gaffer posterior, 90% interval", color=MUTED, fontsize=9)
        ax.set_title(label, color=INK, fontsize=10.5, loc="left")
    fig.suptitle("Team strengths recovered from match data alone", color=INK, fontsize=11, x=0.02,
                 ha="left")
    fig.tight_layout()
    fig.savefig(img / "strength_recovery.png", facecolor=SURFACE)
    plt.close(fig)

    print(json.dumps({k: v for k, v in results.items() if k != "reliability"}, indent=2))


if __name__ == "__main__":
    main()
