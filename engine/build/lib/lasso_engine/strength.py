"""Bayesian team-strength model (pre-match).

Model (per match, home team i, away team j)::

    log lambda_home = mu + H + att_i - def_j
    log lambda_away = mu       + att_j - def_i
    c_home ~ Poisson(lambda_home)        (weighted)
    c_away ~ Poisson(lambda_away)        (weighted)

    att_k ~ Normal(0, sigma_att^2),  def_k ~ Normal(0, sigma_def^2)
    mu ~ Normal(0.2, 1),             H ~ Normal(0.2, 0.2^2)

The observed count ``c`` blends goals with expected goals,
``c = alpha * goals + (1 - alpha) * xG``, which is a standard quasi-likelihood
trick: xG is a much less noisy signal of underlying quality than goals.
Older matches are down-weighted with an exponential time decay so the model
tracks form across seasons (Dixon-Coles style).

The posterior is computed with a Laplace approximation (Newton's method on
the log posterior, then the inverse Hessian as covariance). It is exact up
to a Gaussian approximation, runs in milliseconds, and is validated against
full NUTS sampling in :mod:`lasso_engine.mcmc_check`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import poisson

MATCHDAYS_PER_SEASON = 38


@dataclass(frozen=True)
class StrengthHyper:
    # Tuned on season 4 (trained on seasons 1-3) by ranked probability score.
    sigma_att: float = 0.25
    sigma_def: float = 0.225
    decay_per_matchday: float = 0.02  # half-life of about 35 matchdays
    alpha_goals: float = 0.0  # weight on goals vs xG; xG alone forecast best
    mu_prior: tuple[float, float] = (0.2, 1.0)
    home_prior: tuple[float, float] = (0.2, 0.2)


@dataclass
class StrengthPosterior:
    club_ids: list[str]
    mean: np.ndarray
    cov: np.ndarray
    n_matches: int

    @property
    def n(self) -> int:
        return len(self.club_ids)

    def index(self, club_id: str) -> int:
        return self.club_ids.index(club_id)

    @property
    def mu(self) -> float:
        return float(self.mean[0])

    @property
    def home(self) -> float:
        return float(self.mean[1])

    def attack(self) -> pd.Series:
        return pd.Series(self.mean[2:2 + self.n], index=self.club_ids)

    def defense(self) -> pd.Series:
        return pd.Series(self.mean[2 + self.n:], index=self.club_ids)

    def sd(self) -> np.ndarray:
        return np.sqrt(np.diag(self.cov))

    def _rows(self, home_id: str, away_id: str) -> tuple[np.ndarray, np.ndarray]:
        n = self.n
        i, j = self.index(home_id), self.index(away_id)
        xh = np.zeros(2 + 2 * n)
        xa = np.zeros(2 + 2 * n)
        xh[0] = xa[0] = 1.0
        xh[1] = 1.0
        xh[2 + i] = 1.0
        xh[2 + n + j] = -1.0
        xa[2 + j] = 1.0
        xa[2 + n + i] = -1.0
        return xh, xa

    def expected_goals(self, home_id: str, away_id: str) -> dict[str, float]:
        """Posterior mean and variance of each side's scoring rate (goals per match)."""
        xh, xa = self._rows(home_id, away_id)
        out = {}
        for name, x in (("home", xh), ("away", xa)):
            m = float(x @ self.mean)
            v = float(x @ self.cov @ x)
            # Log-normal moments of exp(eta).
            out[f"{name}_rate"] = float(np.exp(m + v / 2))
            out[f"{name}_rate_var"] = float((np.exp(v) - 1) * np.exp(2 * m + v))
            out[f"{name}_log_mean"] = m
            out[f"{name}_log_sd"] = float(np.sqrt(v))
        return out

    def outcome_probs(self, home_id: str, away_id: str, draws: int = 400,
                      seed: int = 0, max_goals: int = 15) -> dict[str, float]:
        """P(home win), P(draw), P(away win) integrating over parameter uncertainty."""
        xh, xa = self._rows(home_id, away_id)
        rng = np.random.default_rng(seed)
        mh, ma = xh @ self.mean, xa @ self.mean
        cov2 = np.array([[xh @ self.cov @ xh, xh @ self.cov @ xa],
                         [xa @ self.cov @ xh, xa @ self.cov @ xa]])
        eta = rng.multivariate_normal([mh, ma], cov2, size=draws)
        g = np.arange(max_goals + 1)
        ph = poisson.pmf(g[None, :], np.exp(eta[:, :1])).mean(axis=0)
        pa = poisson.pmf(g[None, :], np.exp(eta[:, 1:])).mean(axis=0)
        joint = np.outer(ph, pa)
        joint /= joint.sum()  # renormalise the truncated tail
        return {
            "home": float(np.tril(joint, -1).sum()),
            "draw": float(np.trace(joint)),
            "away": float(np.triu(joint, 1).sum()),
        }


def _design(matches: pd.DataFrame, club_ids: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(club_ids)
    idx = {c: k for k, c in enumerate(club_ids)}
    m = len(matches)
    X = np.zeros((2 * m, 2 + 2 * n))
    hi = matches.home_id.map(idx).to_numpy()
    ai = matches.away_id.map(idx).to_numpy()
    r = np.arange(m)
    X[:, 0] = 1.0
    X[r, 1] = 1.0
    X[r, 2 + hi] = 1.0
    X[r, 2 + n + ai] = -1.0
    X[m + r, 2 + ai] = 1.0
    X[m + r, 2 + n + hi] = -1.0
    return X, hi, ai


def global_matchday(season: np.ndarray | int, matchday: np.ndarray | int):
    return (np.asarray(season) - 1) * MATCHDAYS_PER_SEASON + np.asarray(matchday)


def fit_strength(matches: pd.DataFrame, club_ids: list[str], as_of: int,
                 hyper: StrengthHyper = StrengthHyper(), max_iter: int = 50) -> StrengthPosterior:
    """Laplace posterior given all matches strictly before global matchday ``as_of``."""
    hist = matches[global_matchday(matches.season, matches.matchday) < as_of]
    n = len(club_ids)
    p = 2 + 2 * n
    prior_mean = np.zeros(p)
    prior_prec = np.zeros(p)
    prior_mean[0], prior_prec[0] = hyper.mu_prior[0], 1 / hyper.mu_prior[1] ** 2
    prior_mean[1], prior_prec[1] = hyper.home_prior[0], 1 / hyper.home_prior[1] ** 2
    prior_prec[2:2 + n] = 1 / hyper.sigma_att**2
    prior_prec[2 + n:] = 1 / hyper.sigma_def**2
    theta = prior_mean.copy()
    if len(hist) == 0:
        return StrengthPosterior(club_ids, theta, np.diag(1 / prior_prec), 0)

    X, _, _ = _design(hist, club_ids)
    a = hyper.alpha_goals
    c = np.concatenate([a * hist.home_goals + (1 - a) * hist.home_xg,
                        a * hist.away_goals + (1 - a) * hist.away_xg]).astype(float)
    age = as_of - global_matchday(hist.season, hist.matchday)
    w1 = np.exp(-hyper.decay_per_matchday * np.asarray(age, dtype=float))
    w = np.concatenate([w1, w1])
    P = np.diag(prior_prec)
    for _ in range(max_iter):
        lam = np.exp(X @ theta)
        grad = X.T @ (w * (lam - c)) + prior_prec * (theta - prior_mean)
        H = (X * (w * lam)[:, None]).T @ X + P
        step = np.linalg.solve(H, grad)
        theta -= step
        if np.max(np.abs(step)) < 1e-8:
            break
    lam = np.exp(X @ theta)
    H = (X * (w * lam)[:, None]).T @ X + P
    return StrengthPosterior(club_ids, theta, np.linalg.inv(H), len(hist))
