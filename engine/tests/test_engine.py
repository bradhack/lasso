import math

import numpy as np
import pandas as pd
import pytest

from lasso_engine.explain import COMPONENTS, shapley
from lasso_engine.inplay import Gaffer, InPlayParams, LiveMatch, MatchState, odds_multiplier
from lasso_engine.league import build_league, double_round_robin
from lasso_engine.markets import calibration_points, generate_markets
from lasso_engine.simulator import MatchSimulator, shot_xg
from lasso_engine.strength import fit_strength


@pytest.fixture(scope="module")
def league():
    return build_league(seed=3)


@pytest.fixture(scope="module")
def season(league):
    rng = np.random.default_rng(5)
    sim = MatchSimulator(league, rng)
    fixtures = double_round_robin([c.club_id for c in league.clubs], rng)
    results = []
    for md, pairs in enumerate(fixtures[:12], start=1):
        for i, (h, a) in enumerate(pairs):
            results.append(sim.simulate(f"T-{md}-{i}", 1, md, h, a))
    return results


def test_fixtures_are_a_double_round_robin(league):
    ids = [c.club_id for c in league.clubs]
    fx = double_round_robin(ids, np.random.default_rng(0))
    assert len(fx) == 38
    pairs = [p for md in fx for p in md]
    assert len(pairs) == len(set(pairs)) == 380
    for md in fx:
        teams = [t for p in md for t in p]
        assert len(set(teams)) == 20


def test_xg_is_higher_closer_and_more_central():
    assert shot_xg(6, 0) > shot_xg(12, 0) > shot_xg(25, 0)
    assert shot_xg(10, 0) > shot_xg(10, 12)
    assert shot_xg(8, 0, header=True) < shot_xg(8, 0)


def test_simulator_is_deterministic(league):
    a = MatchSimulator(league, np.random.default_rng(42)).simulate("X", 1, 1, "C01", "C02")
    b = MatchSimulator(league, np.random.default_rng(42)).simulate("X", 1, 1, "C01", "C02")
    assert (a.home_goals, a.away_goals, len(a.events)) == (b.home_goals, b.away_goals, len(b.events))


def test_simulated_matches_look_like_football(season):
    goals = np.mean([r.home_goals + r.away_goals for r in season])
    shots = np.mean([r.home_shots + r.away_shots for r in season])
    passes = [e for r in season for e in r.events if e.type == "pass"]
    completion = np.mean([e.outcome for e in passes])
    assert 2.0 < goals < 3.6
    assert 18 < shots < 32
    assert 0.75 < completion < 0.9
    for r in season:
        shot_goals = sum(1 for e in r.events if e.type == "shot" and e.outcome)
        assert shot_goals == r.home_goals + r.away_goals
        assert r.events[-1].type == "full_time"


def test_strength_model_recovers_quality(league, season):
    df = pd.DataFrame([{k: getattr(r, k) for k in ("season", "matchday", "home_id", "away_id",
                                                   "home_goals", "away_goals", "home_xg", "away_xg")}
                       for r in season])
    clubs = sorted(c.club_id for c in league.clubs)
    post = fit_strength(df, clubs, as_of=13)
    truth = pd.Series({c: league.truth[1][c].attack for c in clubs})
    assert np.corrcoef(post.attack(), truth)[0, 1] > 0.6
    p = post.outcome_probs(clubs[0], clubs[1])
    assert math.isclose(sum(p.values()), 1.0, abs_tol=1e-3)


def test_gaffer_probabilities_are_coherent():
    g = Gaffer(1.6, 1.1, InPlayParams())
    s = MatchState()
    p = g.probabilities(s)
    assert math.isclose(p["home"] + p["draw"] + p["away"], 1.0, abs_tol=1e-6)
    assert p["home"] > p["away"]
    s.finished, s.goals = True, [2, 1]
    assert g.probabilities(s)["home"] == pytest.approx(1.0)


def test_red_card_and_goal_move_the_gaffers_gauge_the_right_way():
    g = Gaffer(1.4, 1.4, InPlayParams())
    live = LiveMatch(g, "H", "A")
    live.apply({"type": "shot", "period": 1, "clock": 10.0, "team_id": "X", "xg": 0.1, "outcome": False})
    base = live.probabilities()["home"]
    live.apply({"type": "red_card", "period": 1, "clock": 12.0, "team_id": "A", "xg": float("nan")})
    after_red = live.probabilities()["home"]
    assert after_red > base
    live.apply({"type": "shot", "period": 1, "clock": 20.0, "team_id": "H", "xg": 0.3, "outcome": True})
    assert live.probabilities()["home"] > after_red
    assert live.state.goals == [1, 0]


def test_shapley_contributions_sum_to_total_change():
    g = Gaffer(1.5, 1.2, InPlayParams())
    a = MatchState(period=2, clock=60, elapsed=62, xg=[0.6, 0.5], exposure=[62, 62])
    b = MatchState(period=2, clock=75, elapsed=77, goals=[1, 0], reds=[0, 1], xg=[1.1, 0.6],
                   exposure=[80, 70])
    att = shapley(g, a, b, "home")
    assert set(att.contributions) == set(COMPONENTS)
    assert sum(att.contributions.values()) == pytest.approx(att.delta, abs=1e-9)
    assert att.contributions["goals"] > 0


def test_markets_and_odds():
    g = Gaffer(1.5, 1.2, InPlayParams())
    s = MatchState(period=2, clock=67, elapsed=69, goals=[1, 1], exposure=[69, 69], xg=[1.0, 0.7])
    mk = generate_markets(g, s, "Harbourside", "Kingsmere")
    assert any("before" in m.question for m in mk)
    for m in mk:
        assert sum(o["p"] for o in m.options) == pytest.approx(1.0, abs=1e-3)
        assert all(1.05 <= o["multiplier"] <= 25 for o in m.options)
    assert odds_multiplier(0.46) == pytest.approx(2.0)
    assert calibration_points(True, 0.9) > calibration_points(True, 0.6)
    assert calibration_points(False, 0.9) < calibration_points(False, 0.6)


def test_season_outlook_is_coherent(league, season):
    from lasso_engine.season import apply_result, outcome_scores, rank, simulate, stake_zone, table_before

    played = pd.DataFrame([{k: getattr(r, k) for k in ("match_id", "season", "matchday", "home_id", "away_id",
                                                       "home_goals", "away_goals", "home_xg", "away_xg")}
                           for r in season])
    ids = [c.club_id for c in league.clubs]
    fx = double_round_robin(ids, np.random.default_rng(5))
    future = pd.DataFrame([{"match_id": f"T-{md}-{i}", "season": 1, "matchday": md, "home_id": h, "away_id": a,
                            "home_goals": 0, "away_goals": 0, "home_xg": 0.0, "away_xg": 0.0}
                           for md, pairs in enumerate(fx, start=1) if md > 12 for i, (h, a) in enumerate(pairs)])
    matches = pd.concat([played, future], ignore_index=True)
    clubs = sorted(ids)
    live = future.iloc[0]

    t = table_before(matches, clubs, 1, 13)
    assert (t.played == 12).all() and t.pts.sum() == 3 * (t.won.sum()) + t.drawn.sum()
    assert t.won.sum() == t.lost.sum() and t.gd.sum() == 0

    o = simulate(matches, clubs, 1, 13, live.home_id, live.away_id, live.match_id, sims=2000, seed=1)
    assert o.remaining == len(future)
    odds = o.odds_given(1, 0)
    # Exactly one champion, four top-four places and three relegated clubs in every simulated season.
    assert math.isclose(sum(v["title"] for v in odds.values()), 1.0, abs_tol=1e-9)
    assert math.isclose(sum(v["top4"] for v in odds.values()), 4.0, abs_tol=1e-9)
    assert math.isclose(sum(v["relegation"] for v in odds.values()), 3.0, abs_tol=1e-9)
    # Winning helps: the home side's top-four chance and average finish are better with a win than a loss.
    cond = o.conditional(0, 0)
    h = live.home_id
    assert cond["home"][h]["top4"] >= cond["away"][h]["top4"]
    assert cond["home"][h]["avg_pos"] < cond["away"][h]["avg_pos"]
    assert stake_zone(cond, h, "home")[0] in ("title", "top4", "relegation", "none")
    # Blending by the live chances stays between the extremes.
    b = o.blended(0, 0, {"home": 0.5, "draw": 0.3, "away": 0.2})
    assert cond["away"][h]["top4"] - 1e-9 <= b[h]["top4"] <= cond["home"][h]["top4"] + 1e-9

    assert outcome_scores(1, 1) == {"home": (2, 1), "draw": (1, 1), "away": (1, 2)}
    assert outcome_scores(2, 0) == {"home": (2, 0), "draw": (2, 2), "away": (2, 3)}
    now = apply_result(t, live.home_id, live.away_id, 2, 0)
    assert now.loc[live.home_id, "pts"] == t.loc[live.home_id, "pts"] + 3 and len(rank(now)) == 20
