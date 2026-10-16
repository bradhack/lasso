"""Season outlook: the league table and what the rest of the season could bring.

From a given matchday, the remaining fixtures are played out many times with the Gaffer's pre-match team
strengths (:mod:`lasso_engine.strength`), drawing the strengths themselves from their posterior each time so
the odds carry the model's uncertainty. Each simulated season ends in a final table, and counting how often a
club finishes first, in the top four or in the bottom three gives its title, top-four and relegation chances.

One match is live. Its result is left out of the simulations and added afterward, so the same simulations
answer "what if it ends 2-1?" for any final score in milliseconds. Weighting the win, draw and loss answers
by the Gaffer's live chances gives season odds that move with every minute of the match.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .strength import StrengthHyper, _design, fit_strength, global_matchday

ZONES = ("title", "top4", "relegation")
TOP = 4
RELEGATED = 3


def table_before(matches: pd.DataFrame, club_ids: list[str], season: int, matchday: int) -> pd.DataFrame:
    """The league table after every match of ``season`` played before ``matchday``."""
    done = matches[(matches.season == season) & (matches.matchday < matchday)]
    t = pd.DataFrame(0, index=club_ids, columns=["played", "won", "drawn", "lost", "gf", "ga", "pts"])
    for r in done.itertuples():
        for club, f, a in ((r.home_id, r.home_goals, r.away_goals), (r.away_id, r.away_goals, r.home_goals)):
            t.loc[club, "played"] += 1
            t.loc[club, "gf"] += f
            t.loc[club, "ga"] += a
            res = "won" if f > a else "drawn" if f == a else "lost"
            t.loc[club, res] += 1
            t.loc[club, "pts"] += 3 if f > a else 1 if f == a else 0
    t["gd"] = t.gf - t.ga
    return t


def rank(t: pd.DataFrame, names: dict[str, str] | None = None) -> list[str]:
    """Club ids in table order: points, then goal difference, then goals scored, then name."""
    names = names or {}
    return sorted(t.index, key=lambda c: (-t.loc[c, "pts"], -t.loc[c, "gd"], -t.loc[c, "gf"], names.get(c, c)))


def apply_result(t: pd.DataFrame, home_id: str, away_id: str, h: int, a: int) -> pd.DataFrame:
    """A copy of the table with one more result in it (the live match as it stands)."""
    t = t.copy()
    for club, f, g in ((home_id, h, a), (away_id, a, h)):
        t.loc[club, "played"] += 1
        t.loc[club, "gf"] += f
        t.loc[club, "ga"] += g
        t.loc[club, "gd"] += f - g
        t.loc[club, "pts"] += 3 if f > g else 1 if f == g else 0
        t.loc[club, "won" if f > g else "drawn" if f == g else "lost"] += 1
    return t


def outcome_scores(h: int, a: int) -> dict[str, tuple[int, int]]:
    """The nearest final score for each result from the current score: the score itself for the result it
    already is, otherwise the fewest extra goals that get there (from 1-1: a home win is 2-1)."""
    return {
        "home": (h, a) if h > a else (a + 1, a),
        "draw": (h, a) if h == a else (max(h, a), max(h, a)),
        "away": (h, a) if a > h else (h, h + 1),
    }


@dataclass
class SeasonOutlook:
    club_ids: list[str]
    season: int
    matchday: int
    home_id: str
    away_id: str
    before: pd.DataFrame
    pts: np.ndarray  # (sims, clubs) final points, excluding the live match
    gd: np.ndarray
    gf: np.ndarray
    tiebreak: np.ndarray
    remaining: int
    _cache: dict = field(default_factory=dict, repr=False)

    @property
    def sims(self) -> int:
        return int(self.pts.shape[0])

    def odds_given(self, h: int, a: int) -> dict[str, dict[str, float]]:
        """Each club's title, top-four and relegation chances, and average finish, if the live match ends h-a."""
        key = (h, a)
        if key in self._cache:
            return self._cache[key]
        i, j = self.club_ids.index(self.home_id), self.club_ids.index(self.away_id)
        pts, gd, gf = self.pts.copy(), self.gd.copy(), self.gf.copy()
        pts[:, i] += 3 if h > a else 1 if h == a else 0
        pts[:, j] += 3 if a > h else 1 if h == a else 0
        gd[:, i] += h - a
        gd[:, j] += a - h
        gf[:, i] += h
        gf[:, j] += a
        score = pts * 1e6 + (gd + 500) * 1e3 + gf + self.tiebreak
        order = np.argsort(-score, axis=1)
        pos = np.empty_like(order)
        rows = np.arange(order.shape[0])[:, None]
        pos[rows, order] = np.arange(1, order.shape[1] + 1)[None, :]
        n = len(self.club_ids)
        out = {}
        for k, club in enumerate(self.club_ids):
            p = pos[:, k]
            out[club] = {"title": float((p == 1).mean()), "top4": float((p <= TOP).mean()),
                         "relegation": float((p > n - RELEGATED).mean()), "avg_pos": float(p.mean())}
        self._cache[key] = out
        return out

    def conditional(self, h: int, a: int) -> dict[str, dict[str, dict[str, float]]]:
        """For each result of the live match (home win, draw, away win), every club's odds."""
        return {res: self.odds_given(*sc) for res, sc in outcome_scores(h, a).items()}

    def blended(self, h: int, a: int, probs: dict[str, float]) -> dict[str, dict[str, float]]:
        """Season odds now: the result odds weighted by the Gaffer's live chances of each result."""
        cond = self.conditional(h, a)
        return {club: {z: sum(probs[r] * cond[r][club][z] for r in cond) for z in (*ZONES, "avg_pos")}
                for club in self.club_ids}


def simulate(matches: pd.DataFrame, club_ids: list[str], season: int, matchday: int, home_id: str, away_id: str,
             live_match_id: str, hyper: StrengthHyper = StrengthHyper(), sims: int = 10_000,
             seed: int = 0) -> SeasonOutlook:
    """Play out the rest of the season ``sims`` times from ``matchday`` (the live match left out)."""
    rng = np.random.default_rng(seed)
    post = fit_strength(matches, club_ids, int(global_matchday(season, matchday)), hyper)
    before = table_before(matches, club_ids, season, matchday)
    rest = matches[(matches.season == season) & (matches.matchday >= matchday) & (matches.match_id != live_match_id)]
    n = len(club_ids)
    pts = np.tile(before.pts.to_numpy(dtype=np.int32), (sims, 1))
    gd = np.tile(before.gd.to_numpy(dtype=np.int32), (sims, 1))
    gf = np.tile(before.gf.to_numpy(dtype=np.int32), (sims, 1))
    if len(rest):
        X, hi, ai = _design(rest, club_ids)
        m = len(rest)
        theta = rng.multivariate_normal(post.mean, post.cov, size=sims)  # strengths drawn from the posterior
        lam = np.exp(theta @ X.T)  # (sims, 2m): home rates then away rates
        goals = rng.poisson(lam).astype(np.int32)
        gh, ga = goals[:, :m], goals[:, m:]
        home = np.zeros((m, n), dtype=np.int32)
        away = np.zeros((m, n), dtype=np.int32)
        home[np.arange(m), hi] = 1
        away[np.arange(m), ai] = 1
        hp = 3 * (gh > ga) + (gh == ga)
        ap = 3 * (ga > gh) + (gh == ga)
        pts += hp @ home + ap @ away
        gd += (gh - ga) @ home + (ga - gh) @ away
        gf += gh @ home + ga @ away
    return SeasonOutlook(club_ids=list(club_ids), season=season, matchday=matchday, home_id=home_id,
                         away_id=away_id, before=before, pts=pts, gd=gd, gf=gf,
                         tiebreak=rng.random((sims, n)) * 0.5, remaining=len(rest) + 1)


def stake_zone(cond: dict[str, dict[str, dict[str, float]]], club: str, side: str) -> tuple[str, float]:
    """The race this match matters most to for one club, and how much: the zone whose chance differs most
    between winning and losing. Near ties (within 1.5 points) go to the hopeful race: title, then top four,
    then relegation, so a club in the top half isn't framed as fighting the drop."""
    win, lose = ("home", "away") if side == "home" else ("away", "home")
    best, spread = "none", 0.0
    for z in ZONES:
        s = abs(cond[win][club][z] - cond[lose][club][z])
        if s > spread + (0.015 if best != "none" else 1e-9):
            best, spread = z, s
    return (best, spread) if spread >= 0.01 else ("none", spread)
