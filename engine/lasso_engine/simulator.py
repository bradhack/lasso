"""Event-level football match simulator.

The simulator produces football-realistic event streams (passes with
difficulty ratings, shots with xG and speed, saves, corners, fouls, cards,
substitutions) from the hidden club truth in :mod:`lasso_engine.league`.

Design: play is modelled as a sequence of possession *chains*. Each chain is
owned by one team and contains a run of passes. A chain either ends in a
turnover (a failed pass, won back by the opponent) or in a shot. The
probability that a chain ends in a shot is set so that each team's shot rate
per minute equals its *target* rate, which is a log-linear function of
attack, defence, home advantage and the in-match state (score, red cards,
late game). That keeps the scoring process faithful to the generative truth
while the event texture stays realistic.
"""

from __future__ import annotations

import math

import numpy as np

from .league import ClubTruth, League
from .schema import PITCH_LENGTH, PITCH_WIDTH, EventType, MatchEvent, MatchResult, Player

# xG model coefficients (logistic in visible goal angle and distance).
XG_B0, XG_B1, XG_B2 = -1.6, 2.2, -0.11
HEADER_XG_MULT = 0.65
PENALTY_XG = 0.78
SHOT_ZONE_P = (0.50, 0.32, 0.18)
PENALTY_SHARE = 0.012  # about one penalty every three to four matches
EXPECTED_MATCH_MINUTES = 95.5  # 90 plus typical added time


def shot_xg(x_to_goal: float, y_offset: float, header: bool = False) -> float:
    """Expected goals from distance to goal line and lateral offset (metres)."""
    half = 3.66
    ang = math.atan2(7.32 * x_to_goal, x_to_goal**2 + y_offset**2 - half**2)
    if ang < 0:
        ang += math.pi
    dist = math.hypot(x_to_goal, y_offset)
    v = 1.0 / (1.0 + math.exp(-(XG_B0 + XG_B1 * ang + XG_B2 * dist)))
    return v * HEADER_XG_MULT if header else v


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


class _Side:
    """Mutable per-team match state."""

    def __init__(self, club_id: str, truth: ClubTruth, squad: list[Player], is_home: bool):
        self.club_id = club_id
        self.truth = truth
        self.is_home = is_home
        by_pos = {p: [pl for pl in squad if pl.position == p] for p in ("GK", "DF", "MF", "FW")}
        self.on_pitch: list[Player] = (
            by_pos["GK"][:1] + by_pos["DF"][:4] + by_pos["MF"][:3] + by_pos["FW"][:3]
        )
        self.bench: list[Player] = [p for p in squad if p not in self.on_pitch and p.position != "GK"][:9]
        self.bench.append(by_pos["GK"][1])
        self.goals = 0
        self.xg = 0.0
        self.shots = 0
        self.reds = 0
        self.yellows: dict[str, int] = {}
        self.subs_made = 0
        self.planned_subs: list[float] = []

    @property
    def gk(self) -> Player:
        return next(p for p in self.on_pitch if p.position == "GK")

    def outfield(self) -> list[Player]:
        return [p for p in self.on_pitch if p.position != "GK"]


class MatchSimulator:
    def __init__(self, league: League, rng: np.random.Generator):
        self.league = league
        self.cfg = league.config
        self.rng = rng

    # ------------------------------------------------------------------ rates
    def base_goal_rates(self, season: int, home_id: str, away_id: str) -> tuple[float, float]:
        """True expected goals per 90 minutes for (home, away) at kickoff."""
        t = self.league.truth[season]
        c = self.cfg
        lh = math.exp(c.base_log_rate + c.home_advantage + t[home_id].attack - t[away_id].defense)
        la = math.exp(c.base_log_rate + t[away_id].attack - t[home_id].defense)
        return lh, la

    def _state_mult(self, me: _Side, opp: _Side, minute: float) -> float:
        c = self.cfg
        m = 1.0
        man_diff = opp.reds - me.reds
        if man_diff < 0:
            m *= c.down_a_man ** (-man_diff)
        elif man_diff > 0:
            m *= c.up_a_man ** man_diff
        if me.goals < opp.goals:
            m *= c.trailing
        elif me.goals > opp.goals:
            m *= c.leading
        if minute >= 75:
            m *= c.late_game
        return m

    # ------------------------------------------------------------- main loop
    def simulate(self, match_id: str, season: int, matchday: int,
                 home_id: str, away_id: str) -> MatchResult:
        rng = self.rng
        lg = self.league
        cfg = self.cfg
        home = _Side(home_id, lg.truth[season][home_id], lg.squads[season][home_id], True)
        away = _Side(away_id, lg.truth[season][away_id], lg.squads[season][away_id], False)
        lam_h, lam_a = self.base_goal_rates(season, home_id, away_id)
        exp_xg_per_shot = cfg.mean_shot_xg
        # Baseline shots per minute so that E[goals] matches the truth rate.
        form_h, form_a = (float(v) for v in rng.normal(0, cfg.match_form_sd, size=2))
        base_shot_rate = {
            home_id: lam_h * math.exp(form_h) / (exp_xg_per_shot * home.truth.finishing) / EXPECTED_MATCH_MINUTES,
            away_id: lam_a * math.exp(form_a) / (exp_xg_per_shot * away.truth.finishing) / EXPECTED_MATCH_MINUTES,
        }
        for side in (home, away):
            n = int(rng.choice([3, 4, 5], p=[0.2, 0.35, 0.45]))
            side.planned_subs = sorted(float(v) for v in rng.uniform(55, 88, size=n))
            if rng.random() < 0.08:  # occasional half-time change
                side.planned_subs[0] = 45.0

        events: list[MatchEvent] = []
        seq = 0

        def emit(period: int, clock: float, side: _Side | None, player: Player | None,
                 etype: str, **kw) -> None:
            nonlocal seq
            seq += 1
            events.append(MatchEvent(
                match_id=match_id, seq=seq, period=period, clock=round(clock, 3),
                team_id=side.club_id if side else None,
                player_id=player.player_id if player else None,
                type=etype, home_score=home.goals, away_score=away.goals, **kw,
            ))

        added_1h = float(rng.choice([1, 2, 3, 4], p=[0.3, 0.35, 0.25, 0.1]))
        added_2h = 0.0
        avg_chain_sec = 26.0
        n_chains = 0
        stats_2h = {"goals": 0, "cards": 0}

        for period in (1, 2):
            if period == 2:  # half-time team talk, tactical changes
                for cid, shift in zip((home_id, away_id), rng.normal(0, cfg.halftime_shift_sd, size=2)):
                    base_shot_rate[cid] *= math.exp(float(shift))
            clock = 0.0 if period == 1 else 45.0
            period_end = 45.0 + added_1h if period == 1 else None
            owner = home if (period == 1) == bool(rng.random() < 0.5) else away
            emit(period, clock, owner, owner.on_pitch[-1], EventType.KICKOFF, x=52.5, y=34.0)
            start_x, start_y = 52.5, 34.0
            while True:
                if period == 2 and period_end is None and clock >= 90.0:
                    added_2h = float(np.clip(round(3 + 0.6 * stats_2h["goals"] + 0.3 * stats_2h["cards"]
                                                   + 0.25 * (home.subs_made + away.subs_made) / 2
                                                   + rng.normal(0, 1.0)), 2, 10))
                    period_end = 90.0 + added_2h
                if period_end is not None and clock >= period_end:
                    break
                for side in (home, away):
                    self._maybe_sub(side, clock, period, emit)

                opp = away if owner is home else home
                # --- possession share for the next chain
                bias = home.truth.possession_bias - away.truth.possession_bias + 0.08
                bias += 0.35 * (away.reds - home.reds)
                if home.goals < away.goals:
                    bias += 0.12
                elif home.goals > away.goals:
                    bias -= 0.12
                p_home = _sigmoid(bias)
                owner = home if rng.random() < p_home else away
                opp = away if owner is home else home
                p_owner = p_home if owner is home else 1 - p_home

                minute = clock
                target_rate = base_shot_rate[owner.club_id] * self._state_mult(owner, opp, minute)
                q_shot = min(0.65, target_rate * avg_chain_sec / (60.0 * p_owner))

                chain_sec, start_x, start_y, ended_shot = self._play_chain(
                    owner, opp, period, clock, q_shot, start_x, start_y, emit, home, away, stats_2h)
                n_chains += 1
                avg_chain_sec += (chain_sec - avg_chain_sec) / min(n_chains, 60)
                # Defensive fouls and cards accumulate over the chain duration.
                self._discipline(opp, owner, period, clock, chain_sec, emit, stats_2h)
                clock += chain_sec / 60.0

            emit(period, clock, None, None,
                 EventType.HALF_TIME if period == 1 else EventType.FULL_TIME)

        return MatchResult(
            match_id=match_id, season=season, matchday=matchday,
            home_id=home_id, away_id=away_id,
            home_goals=home.goals, away_goals=away.goals,
            home_xg=round(home.xg, 3), away_xg=round(away.xg, 3),
            home_shots=home.shots, away_shots=away.shots,
            home_red=home.reds, away_red=away.reds,
            added_1h=added_1h, added_2h=added_2h,
            home_form=round(form_h, 4), away_form=round(form_a, 4), events=events,
        )

    # ----------------------------------------------------------------- chain
    def _pick(self, players: list[Player], weights: list[float]) -> Player:
        w = np.asarray(weights, dtype=float)
        return players[int(self.rng.choice(len(players), p=w / w.sum()))]

    def _play_chain(self, owner: _Side, opp: _Side, period: int, clock: float, q_shot: float,
                    x: float, y: float, emit, home: _Side, away: _Side, stats_2h: dict):
        rng = self.rng
        tr = owner.truth
        is_shot_chain = rng.random() < q_shot
        sec = float(rng.uniform(3, 9))  # restart / dead-ball time
        outfield = owner.outfield()
        weights = [p.involvement for p in outfield]
        carrier = self._pick(outfield, weights)
        # Penalties are a small share of shot chains.
        if is_shot_chain and rng.random() < PENALTY_SHARE:
            sec += 60.0  # foul in the box, VAR check, set-up
            s_sec, nx, ny, _ = self._shoot(owner, opp, period, clock + sec / 60, carrier,
                                           emit, home, away, stats_2h, penalty=True)
            return sec + s_sec, nx, ny, True

        n_target = int(rng.geometric(1 / (1.5 + 4.0 * (1 - tr.directness)))) if is_shot_chain else 99
        n = 0
        while True:
            n += 1
            # --- pass geometry
            fwd_mu = 3 + 12 * tr.directness
            if is_shot_chain and n >= n_target - 1:
                fwd_mu += 10
            dx = float(rng.normal(fwd_mu, 11))
            if x + dx > 100:
                dx = 100 - x - float(rng.uniform(0, 8))
            if x + dx < 3:
                dx = 3 - x + float(rng.uniform(0, 5))
            dy = float(rng.normal(0, 13))
            ex, ey = x + dx, float(np.clip(y + dy, 1.5, PITCH_WIDTH - 1.5))
            length = math.hypot(ex - x, ey - y)
            difficulty = float(np.clip(
                0.55 * _sigmoid((length - 22) / 7) + 0.25 * max(0.0, dx) / 30
                + (0.18 if ex > 75 else 0.0) + float(rng.normal(0, 0.06)), 0.0, 1.0))
            p_success = float(np.clip(carrier.passing * tr.pass_skill * (1.10 - 0.42 * difficulty), 0.25, 0.99))
            success = True if is_shot_chain else bool(rng.random() < p_success)
            speed = float(np.clip(28 + 1.25 * length + rng.normal(0, 6), 18, 110))
            receiver = self._pick([p for p in outfield if p is not carrier] or outfield,
                                  [p.involvement for p in outfield if p is not carrier] or [1.0])
            t_pass = 1.2 + length / max(speed / 3.6, 5.0) + float(rng.uniform(0.8, 3.5))
            sec += t_pass
            emit(period, clock + sec / 60, owner, carrier, EventType.PASS,
                 x=round(x, 1), y=round(y, 1), end_x=round(ex, 1), end_y=round(ey, 1),
                 outcome=success, receiver_id=receiver.player_id if success else None,
                 pass_length=round(length, 1), pass_difficulty=round(difficulty, 3),
                 ball_speed_kmh=round(speed, 1))
            if not success:
                # Opponent wins it back, in their own perspective.
                wx, wy = PITCH_LENGTH - ex, PITCH_WIDTH - ey
                defender = self._pick(opp.outfield(), [1.0 for _ in opp.outfield()])
                emit(period, clock + sec / 60, opp, defender,
                     EventType.INTERCEPTION if rng.random() < 0.55 else EventType.TACKLE,
                     x=round(wx, 1), y=round(wy, 1), outcome=True)
                return sec, wx, wy, False
            x, y, carrier = ex, ey, receiver
            if is_shot_chain and n >= n_target:
                s_sec, nx, ny, _ = self._shoot(owner, opp, period, clock + sec / 60, carrier,
                                               emit, home, away, stats_2h)
                return sec + s_sec, nx, ny, True
            if not is_shot_chain and rng.random() < 0.035:  # ball out of play, retained
                sec += float(rng.uniform(6, 14))
            if n > 40:
                return sec, x, y, False

    def _shoot(self, owner: _Side, opp: _Side, period: int, clock: float, carrier: Player,
               emit, home: _Side, away: _Side, stats_2h: dict, penalty: bool = False):
        rng = self.rng
        outfield = owner.outfield()
        shooter = carrier if penalty else self._pick(
            outfield, [{"FW": 3.0, "MF": 1.4, "DF": 0.4}.get(p.position, 0.1) * p.finishing ** 0.5
                       for p in outfield])
        header = False
        if penalty:
            gx, gy, xg = 11.0, 0.0, PENALTY_XG
        else:
            zone = int(rng.choice(3, p=SHOT_ZONE_P))
            d = (rng.uniform(5.5, 17), rng.uniform(16, 25), rng.uniform(24, 34))[zone]
            gy = float(rng.normal(0, 7.5) * (0.8 if zone == 0 else 1.2))
            gx = math.sqrt(max(d**2 - gy**2, 1.0))
            header = zone == 0 and rng.random() < 0.27
            xg = shot_xg(gx, gy, header)
        sx, sy = PITCH_LENGTH - gx, 34.0 + gy
        fin = shooter.finishing / 1.0 * owner.truth.finishing
        p_goal = min(0.97, xg * (0.85 + 0.15 * fin) if not penalty else xg)
        is_goal = bool(rng.random() < p_goal)
        on_target = is_goal or bool(rng.random() < 0.26)
        speed = float(np.clip((48 if header else 72) + 1.1 * math.hypot(gx, gy) + rng.normal(0, 9), 35, 135))
        owner.shots += 1
        owner.xg += xg
        if is_goal:
            owner.goals += 1
            if period == 2:
                stats_2h["goals"] += 1
        emit(period, clock, owner, shooter, EventType.SHOT, x=round(sx, 1), y=round(sy, 1),
             xg=round(xg, 4), outcome=is_goal, on_target=on_target, ball_speed_kmh=round(speed, 1),
             body_part="head" if header else "foot", is_penalty=penalty)
        sec = 2.0
        if is_goal:
            emit(period, clock + 0.01, owner, shooter, EventType.GOAL, x=round(sx, 1), y=round(sy, 1),
                 xg=round(xg, 4), detail="penalty" if penalty else ("header" if header else "open_play"))
            sec += 55.0  # celebration and restart
            emit(period, clock + sec / 60, opp, opp.on_pitch[-1], EventType.KICKOFF, x=52.5, y=34.0)
            return sec, 52.5, 34.0, True
        if on_target:
            emit(period, clock + 0.01, opp, opp.gk, EventType.SAVE, outcome=True)
        if (on_target or rng.random() < 0.3) and rng.random() < 0.4:
            sec += float(rng.uniform(15, 30))
            taker = self._pick(outfield, [p.involvement for p in outfield])
            emit(period, clock + sec / 60, owner, taker, EventType.CORNER,
                 x=104.5, y=0.5 if rng.random() < 0.5 else 67.5)
            return sec, 95.0, 34.0, False
        return sec + float(rng.uniform(8, 20)), 8.0, 34.0, False

    # ------------------------------------------------------------ discipline
    def _discipline(self, offender: _Side, victim: _Side, period: int, clock: float,
                    chain_sec: float, emit, stats_2h: dict) -> None:
        rng = self.rng
        minute = clock + chain_sec / 60
        mins = chain_sec / 60
        late = 1.2 if minute > 70 else 1.0
        trailing = 1.25 if offender.goals < victim.goals and minute > 55 else 1.0
        disc = offender.truth.discipline
        # Rates per minute *while defending* (roughly half the match).
        foul_rate = 2 * 9.0 / 90
        yellow_rate = 2 * 1.85 / 90 * disc * late * trailing
        red_rate = 2 * 0.02 / 90 * disc * trailing
        outfield = offender.outfield()
        for _ in range(int(rng.poisson(foul_rate * mins))):
            fouler = self._pick(outfield, [1.0 / p.discipline for p in outfield])
            emit(period, minute, offender, fouler, EventType.FOUL,
                 x=round(float(rng.uniform(20, 95)), 1), y=round(float(rng.uniform(5, 63)), 1))
        if rng.random() < yellow_rate * mins:
            # Booked players tread carefully, so a second yellow is less likely.
            p = self._pick(outfield, [p.discipline * {"DF": 1.3, "MF": 1.2, "FW": 0.7}[p.position]
                                      * (0.2 if offender.yellows.get(p.player_id) else 1.0) for p in outfield])
            offender.yellows[p.player_id] = offender.yellows.get(p.player_id, 0) + 1
            stats_2h["cards"] += period == 2
            emit(period, minute, offender, p, EventType.FOUL)
            if offender.yellows[p.player_id] >= 2:
                emit(period, minute, offender, p, EventType.YELLOW_CARD, detail="second_yellow")
                self._send_off(offender, p, period, minute, emit, "second_yellow")
            else:
                emit(period, minute, offender, p, EventType.YELLOW_CARD)
        if rng.random() < red_rate * mins and len(outfield) > 7:
            p = self._pick(outfield, [p.discipline for p in outfield])
            emit(period, minute, offender, p, EventType.FOUL, detail="serious_foul_play")
            self._send_off(offender, p, period, minute, emit, "straight_red")

    def _send_off(self, side: _Side, player: Player, period: int, minute: float, emit, why: str) -> None:
        side.reds += 1
        side.on_pitch = [p for p in side.on_pitch if p is not player]
        emit(period, minute, side, player, EventType.RED_CARD, detail=why)

    def _maybe_sub(self, side: _Side, clock: float, period: int, emit) -> None:
        while side.planned_subs and clock >= side.planned_subs[0] and side.subs_made < 5:
            side.planned_subs.pop(0)
            candidates = [p for p in side.outfield()]
            bench = [p for p in side.bench if p.position != "GK"]
            if not candidates or not bench:
                return
            off = self._pick(candidates, [{"FW": 1.4, "MF": 1.2, "DF": 0.6}[p.position] for p in candidates])
            same = [b for b in bench if b.position == off.position] or bench
            on = same[0]
            side.bench.remove(on)
            side.on_pitch[side.on_pitch.index(off)] = on
            side.subs_made += 1
            emit(period, clock, side, on, EventType.SUBSTITUTION,
                 detail=f"off:{off.player_id}")
