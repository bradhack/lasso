"""Call It: free-to-play micro-predictions priced by the Gaffer.

Players stake biscuits (in-app points, no cash value) on short-horizon
questions. Payout multipliers come straight from the Gaffer's probability,
so "beating the Gaffer" means seeing something the model has not priced in.
"""

from __future__ import annotations

from dataclasses import dataclass

from .inplay import Gaffer, MatchState, odds_multiplier


@dataclass
class Market:
    market_id: str
    question: str
    options: list[dict]  # {id, label, p, multiplier}
    closes_at_clock: float
    settles: str  # machine-readable settlement rule

    def to_dict(self) -> dict:
        return {"market_id": self.market_id, "question": self.question, "options": self.options,
                "closes_at_clock": self.closes_at_clock, "settles": self.settles}


def _opts(pairs: list[tuple[str, str, float]]) -> list[dict]:
    return [{"id": i, "label": label, "p": round(p, 4), "multiplier": odds_multiplier(p)}
            for i, label, p in pairs]


def generate_markets(g: Gaffer, s: MatchState, home_name: str, away_name: str,
                     window: float = 10.0) -> list[Market]:
    """Candidate markets for the current moment; the Game Master agent picks and phrases them."""
    if s.finished:
        return []
    out: list[Market] = []
    tag = f"{s.period}-{int(s.clock)}"
    end_clock = min(s.clock + window, 90.0 if s.period == 2 else 45.0) if s.clock < (90 if s.period == 2 else 45) \
        else s.clock + 3
    mins = max(1.0, end_clock - s.clock)

    for team, name in ((0, home_name), (1, away_name)):
        p = g.p_team_scores_within(s, team, mins)
        out.append(Market(f"score-{team}-{tag}", f"{name} score before {int(end_clock)}'?",
                          _opts([("yes", "Yes", p), ("no", "No", 1 - p)]), s.clock + 1,
                          f"team_goal:{team}:until:{end_clock}"))

    ng = g.p_next_goal(s)
    out.append(Market(f"next-{tag}", "Who scores next?",
                      _opts([("home", home_name, ng["home"]), ("away", away_name, ng["away"]),
                             ("none", "No more goals", ng["none"])]), s.clock + 1, "next_goal"))

    pr = g.probabilities(s)
    diff = s.goals[0] - s.goals[1]
    if diff != 0:
        trailing = 1 if diff > 0 else 0
        name = away_name if trailing == 1 else home_name
        p_not_lose = pr["draw"] + (pr["away"] if trailing == 1 else pr["home"])
        out.append(Market(f"comeback-{tag}", f"Can {name} come back for at least a draw?",
                          _opts([("yes", "Believe", p_not_lose), ("no", "No way", 1 - p_not_lose)]),
                          s.clock + 1, f"not_lose:{trailing}"))
    out.append(Market(f"result-{tag}", "Final result?",
                      _opts([("home", home_name, pr["home"]), ("draw", "Draw", pr["draw"]),
                             ("away", away_name, pr["away"])]), s.clock + 1, "result"))
    return out


def calibration_points(correct: bool, confidence: float) -> int:
    """Bonus points rewarding well-calibrated calls (a proper scoring rule).

    ``confidence`` is the player's stated probability for their pick. Using
    1 - (outcome - confidence)^2 (the Brier score) means honest confidence is
    always the best strategy, which keeps the game fair and teaches intuition
    for probability.
    """
    o = 1.0 if correct else 0.0
    return int(round(100 * (1 - (o - confidence) ** 2)))
