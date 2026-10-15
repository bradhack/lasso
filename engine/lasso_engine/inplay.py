"""The Gaffer: live Bayesian match model.

Each team's scoring rate during the match is uncertain. We start from the
pre-match rate given by the team-strength posterior and treat it as a Gamma
prior. As the match unfolds, the evidence (chances created, measured by xG,
plus goals) updates that Gamma conjugately, with time "exposure" adjusted for
game state: being a man down, trailing or leading, and the late-game surge
all change how fast a team creates chances. The number of goals still to come
is then Negative Binomial (Gamma-Poisson), which gives closed-form win, draw
and loss probabilities for the Believe-o-Meter in microseconds.

    rate_T  ~ Gamma(shape = k + w * evidence_T,  rate = k / r0_T + w * exposure_T)
    remaining_goals_T ~ NegBin(shape, rate / (rate + remaining_minutes * multiplier_T))

``k`` (prior strength), ``w`` (evidence weight) and the goals-versus-xG blend
are tuned by maximum predictive likelihood on training seasons; the state
multipliers are learned by Poisson regression on the same seasons.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, replace

import numpy as np
from scipy.stats import nbinom

MAX_GOALS = 15


@dataclass(frozen=True)
class StateMultipliers:
    down_a_man: float = 0.7
    up_a_man: float = 1.3
    trailing: float = 1.15
    leading: float = 0.88
    late_game: float = 1.08

    def team(self, man_diff: int, goal_diff: int, late: bool) -> float:
        """Multiplier for a team, given (opp reds - own reds) and (own - opp goals)."""
        m = 1.0
        if man_diff < 0:
            m *= self.down_a_man ** (-man_diff)
        elif man_diff > 0:
            m *= self.up_a_man ** man_diff
        if goal_diff < 0:
            m *= self.trailing
        elif goal_diff > 0:
            m *= self.leading
        if late:
            m *= self.late_game
        return m


@dataclass(frozen=True)
class InPlayParams:
    prior_shape: float = 8.0  # k: pseudo-goals of confidence in the pre-match rate
    evidence_weight: float = 0.7  # w
    alpha_goals: float = 0.25  # evidence = alpha * goals + (1 - alpha) * xG
    multipliers: StateMultipliers = field(default_factory=StateMultipliers)
    added_1h: tuple[float, ...] = (1, 2, 2, 3, 3, 4)  # empirical samples
    added_2h: tuple[float, ...] = (3, 4, 5, 5, 6, 7)

    @property
    def expected_total_minutes(self) -> float:
        return 90.0 + float(np.mean(self.added_1h)) + float(np.mean(self.added_2h))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["added_1h"] = list(self.added_1h)
        d["added_2h"] = list(self.added_2h)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "InPlayParams":
        d = dict(d)
        d["multipliers"] = StateMultipliers(**d["multipliers"])
        d["added_1h"] = tuple(d["added_1h"])
        d["added_2h"] = tuple(d["added_2h"])
        return cls(**d)


def _cond_mean_remaining(samples: tuple[float, ...], used: float) -> float:
    """E[added - used | added > used], floored so play never 'ends' early."""
    s = np.asarray(samples, dtype=float)
    over = s[s > used]
    if len(over) == 0:
        return 0.5
    return max(0.5, float(over.mean() - used))


@dataclass
class MatchState:
    period: int = 1
    clock: float = 0.0  # match clock (2nd half restarts at 45)
    elapsed: float = 0.0  # actual minutes played including 1st-half stoppage
    finished: bool = False
    goals: list[int] = field(default_factory=lambda: [0, 0])
    reds: list[int] = field(default_factory=lambda: [0, 0])
    xg: list[float] = field(default_factory=lambda: [0.0, 0.0])
    exposure: list[float] = field(default_factory=lambda: [0.0, 0.0])

    def copy(self) -> "MatchState":
        return replace(self, goals=list(self.goals), reds=list(self.reds),
                       xg=list(self.xg), exposure=list(self.exposure))


class Gaffer:
    """Stateless probability engine for one match, given pre-match rates."""

    def __init__(self, home_rate: float, away_rate: float, params: InPlayParams):
        self.params = params
        self.pre = (home_rate, away_rate)
        total = params.expected_total_minutes
        self.r0 = (home_rate / total, away_rate / total)

    # ----------------------------------------------------------- time model
    def remaining_minutes(self, s: MatchState) -> tuple[float, float]:
        """(expected minutes left, of which in the late-game window)."""
        p = self.params
        e2 = float(np.mean(p.added_2h))
        if s.finished:
            return 0.0, 0.0
        if s.period == 1:
            rest_1h = max(0.0, 45 - s.clock) if s.clock < 45 else 0.0
            stop_1h = _cond_mean_remaining(p.added_1h, max(0.0, s.clock - 45)) if s.clock >= 45 \
                else float(np.mean(p.added_1h))
            return rest_1h + stop_1h + 45 + e2, 15 + e2
        if s.clock < 90:
            rem = 90 - s.clock + e2
            late = min(rem, 90 - max(s.clock, 75) + e2)
            return rem, late
        rem = _cond_mean_remaining(p.added_2h, s.clock - 90)
        return rem, rem

    def multiplier(self, s: MatchState, team: int) -> float:
        opp = 1 - team
        late = s.period == 2 and s.clock >= 75
        return self.params.multipliers.team(s.reds[opp] - s.reds[team], s.goals[team] - s.goals[opp], late)

    def future_multiplier(self, s: MatchState, team: int) -> float:
        opp = 1 - team
        mult = self.params.multipliers
        rem, late = self.remaining_minutes(s)
        if rem <= 0:
            return 1.0
        base = mult.team(s.reds[opp] - s.reds[team], s.goals[team] - s.goals[opp], False)
        frac_late = late / rem
        return base * (frac_late * mult.late_game + (1 - frac_late))

    # ----------------------------------------------------------- posterior
    def posterior(self, s: MatchState, team: int) -> tuple[float, float]:
        p = self.params
        ev = p.alpha_goals * s.goals[team] + (1 - p.alpha_goals) * s.xg[team]
        shape = p.prior_shape + p.evidence_weight * ev
        rate = p.prior_shape / self.r0[team] + p.evidence_weight * s.exposure[team]
        return shape, rate

    def remaining_pmf(self, s: MatchState, team: int) -> np.ndarray:
        rem, _ = self.remaining_minutes(s)
        g = np.arange(MAX_GOALS + 1)
        if rem <= 0:
            out = np.zeros(MAX_GOALS + 1)
            out[0] = 1.0
            return out
        shape, rate = self.posterior(s, team)
        horizon = rem * self.future_multiplier(s, team)
        return nbinom.pmf(g, shape, rate / (rate + horizon))

    def expected_rate(self, s: MatchState, team: int) -> float:
        """Posterior mean goals per minute right now, including game state."""
        shape, rate = self.posterior(s, team)
        return shape / rate * self.multiplier(s, team)

    def probabilities(self, s: MatchState) -> dict[str, float]:
        ph, pa = self.remaining_pmf(s, 0), self.remaining_pmf(s, 1)
        joint = np.outer(ph, pa)
        joint /= joint.sum()  # renormalize the truncated tail
        diff = s.goals[0] - s.goals[1]
        idx = np.arange(MAX_GOALS + 1)
        final_diff = diff + idx[:, None] - idx[None, :]
        return {
            "home": float(joint[final_diff > 0].sum()),
            "draw": float(joint[final_diff == 0].sum()),
            "away": float(joint[final_diff < 0].sum()),
            "home_xg_remaining": float((ph * idx).sum()),
            "away_xg_remaining": float((pa * idx).sum()),
        }

    def p_team_scores_within(self, s: MatchState, team: int, minutes: float) -> float:
        """P(team scores at least once in the next ``minutes`` of play)."""
        shape, rate = self.posterior(s, team)
        rem, _ = self.remaining_minutes(s)
        horizon = min(minutes, rem) * self.multiplier(s, team)
        return float(1 - (rate / (rate + horizon)) ** shape)

    def p_any_goal_within(self, s: MatchState, minutes: float) -> float:
        return 1 - (1 - self.p_team_scores_within(s, 0, minutes)) * (1 - self.p_team_scores_within(s, 1, minutes))

    def p_next_goal(self, s: MatchState) -> dict[str, float]:
        """Which team scores the next goal (or no more goals)."""
        p_none = float(self.remaining_pmf(s, 0)[0] * self.remaining_pmf(s, 1)[0])
        rh, ra = self.expected_rate(s, 0), self.expected_rate(s, 1)
        share = rh / (rh + ra) if rh + ra > 0 else 0.5
        return {"home": float((1 - p_none) * share), "away": float((1 - p_none) * (1 - share)), "none": p_none}


class LiveMatch:
    """Replays a stream of events, maintaining state and the Believe-o-Meter."""

    def __init__(self, gaffer: Gaffer, home_id: str, away_id: str):
        self.g = gaffer
        self.home_id, self.away_id = home_id, away_id
        self.state = MatchState()
        self.added_1h_actual = 0.0

    def _team(self, team_id: str | None) -> int | None:
        if team_id == self.home_id:
            return 0
        if team_id == self.away_id:
            return 1
        return None

    def advance(self, period: int, clock: float) -> None:
        s = self.state
        if period == 2 and s.period == 1:
            # Close out first half exposure, then switch.
            s.period, s.clock = 2, 45.0
        new_elapsed = clock if period == 1 else clock + self.added_1h_actual
        dt = new_elapsed - s.elapsed
        if dt > 0:
            for t in (0, 1):
                s.exposure[t] += dt * self.g.multiplier(s, t)
            s.elapsed = new_elapsed
        s.clock = clock

    def apply(self, ev: dict) -> bool:
        """Apply one event. Returns True if the event can move probabilities."""
        etype = ev["type"]
        period = int(ev["period"])
        clock = float(ev["clock"])
        if etype == "half_time":
            self.advance(1, clock)
            self.added_1h_actual = max(0.0, clock - 45.0)
            return False
        self.advance(period, clock)
        t = self._team(ev.get("team_id"))
        s = self.state
        if etype == "shot" and t is not None:
            xg = ev.get("xg")
            s.xg[t] += float(xg) if xg is not None and xg == xg else 0.0  # NaN-safe
            if ev.get("outcome"):
                s.goals[t] += 1
            return True
        if etype == "red_card" and t is not None:
            s.reds[t] += 1
            return True
        if etype == "full_time":
            s.finished = True
            return True
        return False

    def probabilities(self) -> dict[str, float]:
        return self.g.probabilities(self.state)


RELEVANT_EVENTS = ("shot", "red_card", "half_time", "full_time")


def odds_multiplier(p: float, margin: float = 0.04, cap: float = 25.0) -> float:
    """Biscuit payout multiplier for a call with model probability ``p``."""
    if p <= 0:
        return cap
    return float(min(cap, max(1.05, math.floor((1 - margin) / p * 10) / 10)))
