"""Probabilistic forecast scoring rules."""

from __future__ import annotations

import numpy as np


def outcome_index(home_goals, away_goals) -> np.ndarray:
    """0 = home win, 1 = draw, 2 = away win."""
    h, a = np.asarray(home_goals), np.asarray(away_goals)
    return np.where(h > a, 0, np.where(h == a, 1, 2))


def one_hot(idx: np.ndarray, k: int = 3) -> np.ndarray:
    out = np.zeros((len(idx), k))
    out[np.arange(len(idx)), idx] = 1.0
    return out


def rps(probs: np.ndarray, idx: np.ndarray) -> float:
    """Ranked probability score for ordered 1X2 outcomes (lower is better)."""
    o = one_hot(idx, probs.shape[1])
    cp, co = np.cumsum(probs, axis=1)[:, :-1], np.cumsum(o, axis=1)[:, :-1]
    return float(np.mean(np.sum((cp - co) ** 2, axis=1) / (probs.shape[1] - 1)))


def brier(probs: np.ndarray, idx: np.ndarray) -> float:
    """Multi-class Brier score (lower is better)."""
    return float(np.mean(np.sum((probs - one_hot(idx, probs.shape[1])) ** 2, axis=1)))


def log_loss(probs: np.ndarray, idx: np.ndarray, eps: float = 1e-12) -> float:
    return float(-np.mean(np.log(np.clip(probs[np.arange(len(idx)), idx], eps, 1))))


def reliability(p: np.ndarray, y: np.ndarray, bins: int = 10) -> list[dict]:
    """Binned predicted probability vs observed frequency for a binary event."""
    edges = np.linspace(0, 1, bins + 1)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p < hi if hi < 1 else p <= hi)
        if m.sum():
            out.append({"lo": float(lo), "hi": float(hi), "n": int(m.sum()),
                        "pred": float(p[m].mean()), "obs": float(y[m].mean())})
    return out
