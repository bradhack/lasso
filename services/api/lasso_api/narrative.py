"""Instant, template-based moment packages in four languages.

These are published the moment something happens, so the app never waits on
a language model. When the agents service is available, its richer package
(same ``moment_id``) replaces this one a few seconds later.
"""

from __future__ import annotations

LANGS = ("en", "es", "pt", "fr")

T = {
    "goal": {"en": "Goal: {team} {min}'", "es": "Gol: {team} {min}'", "pt": "Gol: {team} {min}'",
             "fr": "But : {team} {min}'"},
    "red": {"en": "Red card: {team} {min}'", "es": "Roja: {team} {min}'", "pt": "Vermelho: {team} {min}'",
            "fr": "Rouge : {team} {min}'"},
    "chances": {"en": "Chances created ({xg} xG)", "es": "Ocasiones creadas ({xg} xG)",
                "pt": "Chances criadas ({xg} xG)", "fr": "Occasions créées ({xg} xG)"},
    "clock": {"en": "Clock running down", "es": "El reloj corre", "pt": "O relógio corre",
              "fr": "Le chrono tourne"},
    "h_goal": {"en": "{player} scores for {team}!", "es": "¡Gol de {player} para {team}!",
               "pt": "Gol de {player} para o {team}!", "fr": "But de {player} pour {team} !"},
    "h_red": {"en": "Red card! {team} down to ten", "es": "¡Roja! {team} se queda con diez",
              "pt": "Vermelho! {team} fica com dez", "fr": "Carton rouge ! {team} à dix"},
    "h_swing": {"en": "Momentum swings to {team}", "es": "El partido se inclina hacia {team}",
                "pt": "O jogo pende para o {team}", "fr": "Le match bascule vers {team}"},
    "h_swing_draw": {"en": "The draw is closing in", "es": "El empate gana fuerza",
                     "pt": "O empate ganha força", "fr": "Le nul se rapproche"},
    "h_pulse": {"en": "{min}': Believe-o-Meter check", "es": "{min}': así está el Believe-o-Meter",
                "pt": "{min}': como está o Believe-o-Meter", "fr": "{min}' : le point Believe-o-Meter"},
    "h_half_time": {"en": "Half-time: {home} {hs}-{as_} {away}", "es": "Descanso: {home} {hs}-{as_} {away}",
                    "pt": "Intervalo: {home} {hs}-{as_} {away}", "fr": "Mi-temps : {home} {hs}-{as_} {away}"},
    "h_full_time": {"en": "Full-time: {home} {hs}-{as_} {away}", "es": "Final: {home} {hs}-{as_} {away}",
                    "pt": "Fim de jogo: {home} {hs}-{as_} {away}",
                    "fr": "Fin du match : {home} {hs}-{as_} {away}"},
    "h_kickoff": {"en": "Kick-off: {home} v {away}", "es": "Comienza: {home} vs {away}",
                  "pt": "Começa: {home} x {away}", "fr": "Coup d'envoi : {home} - {away}"},
    "story": {"en": "{team} win chance: {a}% to {b}%. Biggest factor: {label} ({d:+d} pts).",
              "es": "Probabilidad de victoria de {team}: del {a}% al {b}%. Factor clave: {label} ({d:+d} pts).",
              "pt": "Chance de vitória ({team}): de {a}% para {b}%. Fator principal: {label} ({d:+d} pts).",
              "fr": "Chances de victoire ({team}) : de {a} % à {b} %. Facteur clé : {label} ({d:+d} pts)."},
    "story_flat": {"en": "{team} win chance holds at {b}%. The Gaffer sees a tight one.",
                   "es": "La probabilidad de {team} se mantiene en el {b}%. Partido igualado.",
                   "pt": "A chance do {team} segue em {b}%. Jogo equilibrado.",
                   "fr": "Les chances de {team} restent à {b} %. Match serré."},
    "up": {"en": "Believe! {team} are up to {p}%.", "es": "¡A creer! {team} sube al {p}%.",
           "pt": "Acredite! {team} sobe para {p}%.", "fr": "Y croire ! {team} grimpe à {p} %."},
    "down": {"en": "Hold your nerve. {team} still sit at {p}%.", "es": "Calma. {team} sigue con un {p}%.",
             "pt": "Calma. {team} ainda tem {p}%.", "fr": "Gardez la foi. {team} reste à {p} %."},
}


def tr(key: str, lang: str, **kw) -> str:
    return T[key][lang].format(**kw)


def driver_rows(contrib: dict[str, float], window: dict, names: tuple[str, str], focus: int) -> list[dict]:
    """Shapley contributions to labelled, localised driver rows (deltas in points)."""
    rows = []
    for comp, delta in sorted(contrib.items(), key=lambda kv: -abs(kv[1])):
        pts = round(delta * 100)
        if comp == "goals" and window["goals"]:
            g = window["goals"][-1]
            labels = {lang: tr("goal", lang, team=names[g["team"]], min=g["minute"]) for lang in LANGS}
            if len(window["goals"]) > 1:
                labels = {lang: v + f" (+{len(window['goals']) - 1})" for lang, v in labels.items()}
        elif comp == "red_cards" and window["reds"]:
            r = window["reds"][-1]
            labels = {lang: tr("red", lang, team=names[r["team"]], min=r["minute"]) for lang in LANGS}
        elif comp == "chances":
            xg = window["xg"][focus]
            labels = {lang: tr("chances", lang, xg=f"{xg:.2f}") for lang in LANGS}
        elif comp == "clock":
            labels = {lang: tr("clock", lang) for lang in LANGS}
        else:
            continue
        if pts == 0:
            continue
        rows.append({"component": comp, "delta": pts, "label": labels})
    return rows


def template_package(*, trigger: str, names: tuple[str, str], score: tuple[int, int], minute: int,
                     before: dict, after: dict, focus: int, drivers: list[dict], scorer: str | None,
                     red_team: int | None, stats: dict) -> dict:
    side = "home" if focus == 0 else "away"
    a, b = round(before[side] * 100), round(after[side] * 100)
    team = names[focus]
    fmt = {"home": names[0], "away": names[1], "hs": score[0], "as_": score[1], "min": minute}
    headline = {}
    for lang in LANGS:
        if trigger == "goal":
            headline[lang] = tr("h_goal", lang, player=scorer or team, team=team)
        elif trigger == "red_card":
            headline[lang] = tr("h_red", lang, team=names[red_team if red_team is not None else focus])
        elif trigger in ("half_time", "full_time", "kickoff"):
            headline[lang] = tr(f"h_{trigger}", lang, **fmt)
        elif trigger == "swing":
            headline[lang] = tr("h_swing", lang, team=team)
        elif trigger == "swing_draw":
            headline[lang] = tr("h_swing_draw", lang)
        else:
            headline[lang] = tr("h_pulse", lang, min=minute)
    top = drivers[0] if drivers else None
    story = {}
    for lang in LANGS:
        if top and abs(top["delta"]) >= 1:
            story[lang] = tr("story", lang, team=team, a=a, b=b, label=top["label"][lang], d=top["delta"])
        else:
            story[lang] = tr("story_flat", lang, team=team, b=b)
    club_lines = {}
    for i, key in ((0, "home"), (1, "away")):
        p_now = round(after["home" if i == 0 else "away"] * 100)
        p_was = round(before["home" if i == 0 else "away"] * 100)
        club_lines[key] = {lang: tr("up" if p_now >= p_was else "down", lang, team=names[i], p=p_now)
                           for lang in LANGS}
    h, aw = stats["teams"]
    contrib_txt = ", ".join(f"{d['component'].replace('_', ' ')} {d['delta']:+d}" for d in drivers)
    analyst = (f"xG {h['xg']:.2f}-{aw['xg']:.2f} · shots {h['shots']}-{aw['shots']} · possession "
               f"{h['possession']}%-{aw['possession']}% · field tilt {h['field_tilt']}%-{aw['field_tilt']}%. "
               f"Shapley on {team} win: {contrib_txt or 'no material change'}.")
    return {"headline": headline, "story": story, "analyst": {"en": analyst}, "club_lines": club_lines,
            "source": "template"}
