"""Synthetic league construction: clubs, squads, fixtures and hidden truth.

The *truth* (each club's true attacking and defensive strength, style and
discipline per season) drives the simulator. It is written to a separate
``truth`` table that the prediction model never reads, so we can later
measure how well the Bayesian model recovers it.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

from .names import CLUBS, player_name
from .schema import Club, Player


@dataclass(frozen=True)
class LeagueConfig:
    """Global generative parameters, tuned to top-flight league-wide averages.

    Calibration targets (approximate published league-wide averages for a
    top European division): ~2.7-2.9 goals per match, ~44% home wins,
    ~24% draws, ~25 shots per match, ~80-84% pass completion, ~3.5-4.5 yellow
    cards per match and roughly one red card every 8-10 matches.
    """

    n_seasons: int = 5
    base_log_rate: float = float(np.log(1.16))  # goals per team per 90 vs average opposition
    home_advantage: float = 0.19  # log-scale boost to the home side's scoring rate
    attack_quality_load: float = 0.21
    attack_noise: float = 0.09
    defense_quality_load: float = 0.17
    defense_noise: float = 0.08
    season_autocorr: float = 0.88
    squad_turnover: int = 4
    # In-match state effects (multipliers on a team's chance creation).
    down_a_man: float = 0.68
    up_a_man: float = 1.32
    trailing: float = 1.16
    leading: float = 0.87
    late_game: float = 1.08  # after the 75th minute
    mean_shot_xg: float = 0.112  # includes the small share of penalties
    # Match-level variation: line-ups, tactics, fatigue, weather, an off day.
    # Hidden from the model; this is what in-play evidence can reveal.
    match_form_sd: float = 0.22
    halftime_shift_sd: float = 0.12


@dataclass
class ClubTruth:
    club_id: str
    season: int
    quality: float
    attack: float
    defense: float
    possession_bias: float
    pass_skill: float
    discipline: float
    finishing: float
    directness: float


@dataclass
class League:
    config: LeagueConfig
    clubs: list[Club]
    squads: dict[int, dict[str, list[Player]]] = field(default_factory=dict)
    truth: dict[int, dict[str, ClubTruth]] = field(default_factory=dict)

    def club(self, club_id: str) -> Club:
        return next(c for c in self.clubs if c.club_id == club_id)


def _make_squad(rng: np.random.Generator, club_id: str, quality: float,
                used: set[str], start_index: int = 0) -> list[Player]:
    layout = [("GK", 3), ("DF", 8), ("MF", 8), ("FW", 5)]
    shirts = iter(rng.permutation(np.arange(1, 40)))
    squad: list[Player] = []
    idx = start_index
    for pos, n in layout:
        for _ in range(n):
            squad.append(_new_player(rng, club_id, pos, int(next(shirts)), quality, used, idx))
            idx += 1
    # Goalkeepers wear 1, 13 or 31 by convention.
    for gk, shirt in zip([p for p in squad if p.position == "GK"], (1, 13, 31)):
        gk.shirt = shirt
    return squad


def _new_player(rng: np.random.Generator, club_id: str, pos: str, shirt: int,
                quality: float, used: set[str], idx: int) -> Player:
    base_pass = {"GK": 0.74, "DF": 0.84, "MF": 0.87, "FW": 0.77}[pos]
    base_fin = {"GK": 0.3, "DF": 0.8, "MF": 0.95, "FW": 1.08}[pos]
    involve = {"GK": 0.35, "DF": 1.0, "MF": 1.35, "FW": 0.85}[pos]
    return Player(
        player_id=f"{club_id}-{idx:03d}",
        club_id=club_id,
        name=player_name(rng, used),
        position=pos,
        shirt=shirt,
        passing=float(np.clip(base_pass + 0.03 * quality + rng.normal(0, 0.025), 0.6, 0.95)),
        finishing=float(np.clip(base_fin * np.exp(0.05 * quality + rng.normal(0, 0.08)), 0.2, 1.5)),
        discipline=float(np.exp(rng.normal(0, 0.25))),
        involvement=float(involve * np.exp(rng.normal(0, 0.2))),
    )


def build_league(seed: int = 7, config: LeagueConfig | None = None) -> League:
    """Create the league, its squads for every season and the hidden truth."""
    cfg = config or LeagueConfig()
    rng = np.random.default_rng(seed)
    clubs = [Club(f"C{i + 1:02d}", n, s, m, p, sec) for i, (n, s, m, p, sec) in enumerate(CLUBS)]
    league = League(cfg, clubs)
    used: set[str] = set()

    rho = cfg.season_autocorr
    quality = {c.club_id: float(rng.normal()) for c in clubs}
    att_eps = {c.club_id: float(rng.normal(0, cfg.attack_noise)) for c in clubs}
    def_eps = {c.club_id: float(rng.normal(0, cfg.defense_noise)) for c in clubs}
    style = {c.club_id: (float(rng.normal()), float(rng.normal())) for c in clubs}

    for season in range(1, cfg.n_seasons + 1):
        if season > 1:  # stationary AR(1) drift between seasons
            innov = np.sqrt(1 - rho**2)
            for cid in quality:
                quality[cid] = rho * quality[cid] + innov * float(rng.normal())
                att_eps[cid] = rho * att_eps[cid] + innov * float(rng.normal(0, cfg.attack_noise))
                def_eps[cid] = rho * def_eps[cid] + innov * float(rng.normal(0, cfg.defense_noise))
        # Centre so the league average attack/defence is zero each season.
        q_mean = np.mean(list(quality.values()))
        a_mean = np.mean(list(att_eps.values()))
        d_mean = np.mean(list(def_eps.values()))

        league.truth[season] = {}
        league.squads[season] = {}
        for c in clubs:
            cid = c.club_id
            q = quality[cid] - q_mean
            s1, s2 = style[cid]
            league.truth[season][cid] = ClubTruth(
                club_id=cid,
                season=season,
                quality=q,
                attack=cfg.attack_quality_load * q + att_eps[cid] - a_mean,
                defense=cfg.defense_quality_load * q + def_eps[cid] - d_mean,
                possession_bias=0.18 * q + 0.15 * s1,
                pass_skill=float(np.clip(1 + 0.025 * q + 0.015 * s1, 0.9, 1.1)),
                discipline=float(np.exp(0.2 * s2 - 0.05 * q)),
                finishing=float(np.exp(0.03 * q + 0.03 * s2)),
                directness=float(np.clip(0.5 - 0.15 * s1, 0.15, 0.85)),
            )
            if season == 1:
                squad = _make_squad(rng, cid, q, used)
            else:
                prev = [replace(p) for p in league.squads[season - 1][cid]]
                outfield = [i for i, p in enumerate(prev) if p.position != "GK"]
                for j in rng.choice(outfield, size=cfg.squad_turnover, replace=False):
                    old = prev[j]
                    prev[j] = _new_player(rng, cid, old.position, old.shirt, q, used,
                                          100 * season + int(j))
                squad = prev
            league.squads[season][cid] = squad
    return league


def double_round_robin(club_ids: list[str], rng: np.random.Generator) -> list[list[tuple[str, str]]]:
    """Return 2(n-1) matchdays of (home, away) pairs using the circle method."""
    ids = list(rng.permutation(club_ids))
    n = len(ids)
    first_half: list[list[tuple[str, str]]] = []
    for r in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = ids[i], ids[n - 1 - i]
            pairs.append((a, b) if (r + i) % 2 == 0 else (b, a))
        first_half.append(pairs)
        ids = [ids[0]] + [ids[-1]] + ids[1:-1]
    second_half = [[(b, a) for a, b in md] for md in first_half]
    return first_half + second_half
