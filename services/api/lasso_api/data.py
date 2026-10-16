"""Loads the demo pack: clubs, players, the held-out season's events and the Gaffer."""

from __future__ import annotations

import contextlib

import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import pandas as pd

from lasso_engine.inplay import InPlayParams
from lasso_engine.strength import StrengthHyper

EVENT_COLUMNS = ["match_id", "seq", "period", "clock", "team_id", "player_id", "type", "x", "y", "end_x",
                 "end_y", "outcome", "receiver_id", "pass_length", "pass_difficulty", "ball_speed_kmh", "xg",
                 "body_part", "on_target", "is_penalty", "detail", "home_score", "away_score"]


def _clean(v):
    if v is None:
        return None
    # NaN is the only value not equal to itself; arrays can't answer that question, and that's fine.
    with contextlib.suppress(TypeError, ValueError):
        if v != v:
            return None
    if hasattr(v, "item"):
        return v.item()
    return v


@dataclass
class DemoData:
    root: Path

    @cached_property
    def clubs(self) -> dict[str, dict]:
        df = pd.read_parquet(self.root / "clubs.parquet")
        return {r.club_id: r._asdict() for r in df.itertuples(index=False)}

    @cached_property
    def players(self) -> dict[str, dict]:
        df = pd.read_parquet(self.root / "players.parquet")
        return {r.player_id: r._asdict() for r in df.itertuples(index=False)}

    @cached_property
    def matches(self) -> dict[str, dict]:
        df = pd.read_parquet(self.root / "matches.parquet")
        return {r.match_id: r._asdict() for r in df.itertuples(index=False)}

    @cached_property
    def matches_df(self) -> pd.DataFrame:
        return pd.read_parquet(self.root / "matches.parquet")

    @cached_property
    def club_ids(self) -> list[str]:
        return sorted(self.clubs)

    @cached_property
    def strength_hyper(self) -> StrengthHyper:
        h = self.model_meta.get("strength_hyper", {})
        return StrengthHyper(**{k: tuple(v) if isinstance(v, list) else v for k, v in h.items()})

    @cached_property
    def prematch(self) -> dict[str, dict]:
        df = pd.read_parquet(self.root / "prematch.parquet")
        return {r.match_id: r._asdict() for r in df.itertuples(index=False)}

    @cached_property
    def _events(self) -> pd.DataFrame:
        return pd.read_parquet(self.root / "events.parquet", columns=EVENT_COLUMNS)

    def events_for(self, match_id: str) -> list[dict]:
        df = self._events[self._events.match_id == match_id].sort_values("seq")
        return [{k: _clean(v) for k, v in rec.items()} for rec in df.to_dict("records")]

    @cached_property
    def params(self) -> InPlayParams:
        model = json.loads((self.root / "gaffer.json").read_text())
        return InPlayParams.from_dict(model["inplay"])

    @cached_property
    def model_meta(self) -> dict:
        return json.loads((self.root / "gaffer.json").read_text())

    def club_name(self, club_id: str | None) -> str:
        return self.clubs[club_id]["name"] if club_id in self.clubs else ""

    def player_label(self, player_id: str | None) -> str:
        p = self.players.get(player_id or "")
        return p["name"] if p else ""
