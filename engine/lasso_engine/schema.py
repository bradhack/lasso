"""Canonical event and entity schema for Lasso.

Pitch coordinates are metres on a 105 x 68 pitch. ``x`` runs from the acting
team's own goal line (0) to the opponent's goal line (105); ``y`` runs from
the left touchline (0) to the right (68). Every event is expressed from the
acting team's attacking perspective, which keeps downstream analytics simple.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0


class EventType:
    KICKOFF = "kickoff"
    PASS = "pass"
    CARRY = "carry"
    TACKLE = "tackle"
    INTERCEPTION = "interception"
    FOUL = "foul"
    SHOT = "shot"
    SAVE = "save"
    GOAL = "goal"
    CORNER = "corner"
    YELLOW_CARD = "yellow_card"
    RED_CARD = "red_card"
    SUBSTITUTION = "substitution"
    HALF_TIME = "half_time"
    FULL_TIME = "full_time"

    ALL = (
        KICKOFF, PASS, CARRY, TACKLE, INTERCEPTION, FOUL, SHOT, SAVE, GOAL,
        CORNER, YELLOW_CARD, RED_CARD, SUBSTITUTION, HALF_TIME, FULL_TIME,
    )


@dataclass(slots=True)
class Club:
    club_id: str
    name: str
    short: str
    monogram: str
    primary: str
    secondary: str


@dataclass(slots=True)
class Player:
    player_id: str
    club_id: str
    name: str
    position: str  # GK, DF, MF, FW
    shirt: int
    # Hidden skill attributes (truth). Never exposed to the model.
    passing: float = 0.8
    finishing: float = 1.0
    discipline: float = 1.0
    involvement: float = 1.0


@dataclass(slots=True)
class MatchEvent:
    match_id: str
    seq: int
    period: int
    clock: float  # match minute as a float, continuous through stoppage time
    team_id: str | None
    player_id: str | None
    type: str
    x: float | None = None
    y: float | None = None
    end_x: float | None = None
    end_y: float | None = None
    outcome: bool | None = None
    receiver_id: str | None = None
    pass_length: float | None = None
    pass_difficulty: float | None = None
    ball_speed_kmh: float | None = None
    xg: float | None = None
    body_part: str | None = None
    on_target: bool | None = None
    is_penalty: bool | None = None
    detail: str | None = None
    home_score: int = 0
    away_score: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MatchResult:
    match_id: str
    season: int
    matchday: int
    home_id: str
    away_id: str
    home_goals: int
    away_goals: int
    home_xg: float
    away_xg: float
    home_shots: int
    away_shots: int
    home_red: int
    away_red: int
    added_1h: float
    added_2h: float
    # Hidden match-level truth (split into truth/ by the generator).
    home_form: float = 0.0
    away_form: float = 0.0
    events: list[MatchEvent] = field(default_factory=list, repr=False)
