"""Why did the Gaffer's Gauge move? Exact Shapley attribution.

Between two moments A and B in a match, four things can change:

* **goals**     the score
* **red_cards** players sent off
* **chances**   attacking evidence (xG created)
* **clock**     time passing (and the exposure that comes with it)

We evaluate the Gaffer's probability for every mix of "component taken from
A" and "component taken from B" (2^4 = 16 evaluations) and compute each
component's Shapley value. The values sum exactly to the total change, so
every point of movement is accounted for, and the attribution does not depend
on the order in which things happened.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

from .inplay import Gaffer, MatchState

COMPONENTS = ("goals", "red_cards", "chances", "clock")


def _mix(a: MatchState, b: MatchState, take_b: frozenset[str]) -> MatchState:
    s = a.copy()
    if "goals" in take_b:
        s.goals = list(b.goals)
    if "red_cards" in take_b:
        s.reds = list(b.reds)
    if "chances" in take_b:
        s.xg = list(b.xg)
    if "clock" in take_b:
        s.period, s.clock, s.elapsed, s.finished = b.period, b.clock, b.elapsed, b.finished
        s.exposure = list(b.exposure)
    return s


@dataclass
class Attribution:
    outcome: str
    before: float
    after: float
    contributions: dict[str, float]

    @property
    def delta(self) -> float:
        return self.after - self.before


def shapley(gaffer: Gaffer, a: MatchState, b: MatchState, outcome: str = "home") -> Attribution:
    """Shapley decomposition of the change in P(outcome) from state ``a`` to ``b``."""
    cache: dict[frozenset[str], float] = {}

    def v(S: frozenset[str]) -> float:
        if S not in cache:
            cache[S] = gaffer.probabilities(_mix(a, b, S))[outcome]
        return cache[S]

    n = len(COMPONENTS)
    contrib = {}
    for c in COMPONENTS:
        others = [x for x in COMPONENTS if x != c]
        total = 0.0
        for r in range(n):
            for S in itertools.combinations(others, r):
                S = frozenset(S)
                weight = math.factorial(len(S)) * math.factorial(n - len(S) - 1) / math.factorial(n)
                total += weight * (v(S | {c}) - v(S))
        contrib[c] = total
    return Attribution(outcome, v(frozenset()), v(frozenset(COMPONENTS)), contrib)
