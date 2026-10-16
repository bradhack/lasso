"""Player impact: how much each player's actions moved their team's chances.

A team's standing in a match is its chance of winning plus half its chance of a draw (a draw counts as half a
win), so an equalizer is valued as well as a winner. A player's impact is the change their actions made to
that number, in percentage points, as measured by the Gaffer at the moment of the action:

* a goal: the whole swing it caused; whoever passed to the scorer gets a quarter of it on top (the assist)
* a shot that doesn't go in: the small lift it gives the Gaffer's view of the team's attack
* a save: the goal prevented, the swing a goal would have caused times the chance the shot had (its xG)
* a red card: the swing against the player's own team

Clock time is nobody's doing, so it isn't credited to anyone.
"""

from __future__ import annotations

from .inplay import Gaffer, MatchState

ASSIST_SHARE = 0.25


def standing(probs: dict[str, float], team: int) -> float:
    """A team's chance of winning plus half its chance of a draw."""
    return probs["home" if team == 0 else "away"] + 0.5 * probs["draw"]


def swing(g: Gaffer, before: MatchState, after: MatchState, team: int) -> float:
    """Change in ``team``'s standing between two states, in percentage points."""
    return 100 * (standing(g.probabilities(after), team) - standing(g.probabilities(before), team))


def goal_prevented(g: Gaffer, state: MatchState, keeper_team: int, xg: float) -> float:
    """A save's value in percentage points: the swing a goal would have caused, times the shot's xG."""
    hyp = state.copy()
    hyp.goals[1 - keeper_team] += 1
    return 100 * max(0.0, xg) * (standing(g.probabilities(state), keeper_team) - standing(g.probabilities(hyp), keeper_team))
