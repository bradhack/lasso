"""Instant, template-based moment packages in four languages.

These are published the moment something happens, so the app never waits on
a language model. When the agents service is available, its richer package
(same ``moment_id``) replaces this one a few seconds later.
"""

from __future__ import annotations

import re

LANGS = ("en", "es", "pt", "fr")

T = {
    "goal": {"en": "Goal: {team} {min}'", "es": "Gol: {team} {min}'", "pt": "Gol: {team} {min}'",
             "fr": "But : {team} {min}'"},
    "red": {"en": "Red card: {team} {min}'", "es": "Roja: {team} {min}'", "pt": "Vermelho: {team} {min}'",
            "fr": "Rouge : {team} {min}'"},
    "chances": {"en": "Chances: xG {h} v {a}", "es": "Ocasiones: xG {h} a {a}",
                "pt": "Chances: xG {h} x {a}", "fr": "Occasions : xG {h} - {a}"},
    "clock": {"en": "Clock running down", "es": "El reloj corre", "pt": "O relógio corre",
              "fr": "Le chrono tourne"},
    "h_goal": {"en": "{player} scores for {team}!", "es": "¡Gol de {player} para {team}!",
               "pt": "Gol de {player} para o {team}!", "fr": "But de {player} pour {team} !"},
    "h_goal_var": {"en": "{player} scores for {team}, and VAR says it stands!",
                   "es": "¡Gol de {player} para {team}, y el VAR lo da por bueno!",
                   "pt": "Gol de {player} para o {team}, e o VAR confirma!",
                   "fr": "But de {player} pour {team}, et la VAR le valide !"},
    "h_var_out": {"en": "No goal! VAR rules out {player}'s strike", "es": "¡No es gol! El VAR anula el tanto de {player}",
                  "pt": "Não vale! O VAR anula o gol de {player}", "fr": "Pas de but ! La VAR refuse le but de {player}"},
    "var_story": {"en": "VAR rules out {player}'s goal for {reason}. {poss} chance of winning stays at {b}%, not the {s}% it would have been.",
                  "es": "El VAR anula el gol de {player} por {reason}. La probabilidad de victoria de {team} se queda en el {b}%, en vez del {s}% que habría tenido.",
                  "pt": "O VAR anula o gol de {player} por {reason}. A chance de vitória do {team} fica em {b}%, em vez dos {s}% que teria.",
                  "fr": "La VAR refuse le but de {player} pour {reason}. Pour {team}, les chances de victoire restent à {b} %, au lieu de {s} %."},
    "r_offside": {"en": "offside", "es": "fuera de juego", "pt": "impedimento", "fr": "hors-jeu"},
    "r_handball": {"en": "handball", "es": "mano", "pt": "toque de mão", "fr": "main"},
    "r_foul": {"en": "a foul in the build-up", "es": "falta previa", "pt": "falta no lance", "fr": "faute en amont"},
    # The analyst paragraph, in every language (the agents' version replaces it when it arrives).
    "analyst": {"en": "xG {hx}-{ax} · shots {hs}-{as_} · possession {hp}%-{ap}% · field tilt {ht}%-{at}%. Change in {team}'s win chance by cause: {drivers}.",
                "es": "xG {hx}-{ax} · tiros {hs}-{as_} · posesión {hp}%-{ap}% · dominio territorial {ht}%-{at}%. Cambio en la probabilidad de {team} por causa: {drivers}.",
                "pt": "xG {hx}-{ax} · chutes {hs}-{as_} · posse {hp}%-{ap}% · domínio territorial {ht}%-{at}%. Variação na chance do {team} por causa: {drivers}.",
                "fr": "xG {hx}-{ax} · tirs {hs}-{as_} · possession {hp} %-{ap} % · territoire {ht} %-{at} %. Variation des chances de {team} par cause : {drivers}."},
    "no_change": {"en": "no material change", "es": "sin cambios relevantes", "pt": "sem mudança relevante",
                  "fr": "pas de changement notable"},
    "h_red": {"en": "Red card! {team} down to ten", "es": "¡Roja! {team} se queda con diez",
              "pt": "Vermelho! {team} fica com dez", "fr": "Carton rouge ! {team} à dix"},
    "h_swing": {"en": "Momentum swings to {team}", "es": "El partido se inclina hacia {team}",
                "pt": "O jogo pende para o {team}", "fr": "Le match bascule vers {team}"},
    "h_swing_draw": {"en": "The draw is closing in", "es": "El empate gana fuerza",
                     "pt": "O empate ganha força", "fr": "Le nul se rapproche"},
    "h_pulse": {"en": "{min}': where it stands", "es": "{min}': así está el partido",
                "pt": "{min}': como está o jogo", "fr": "{min}' : le point du match"},
    "h_half_time": {"en": "Halftime: {home} {hs}-{as_} {away}", "es": "Descanso: {home} {hs}-{as_} {away}",
                    "pt": "Intervalo: {home} {hs}-{as_} {away}", "fr": "Mi-temps : {home} {hs}-{as_} {away}"},
    "h_full_time": {"en": "Full time: {home} {hs}-{as_} {away}", "es": "Final: {home} {hs}-{as_} {away}",
                    "pt": "Fim de jogo: {home} {hs}-{as_} {away}",
                    "fr": "Fin du match : {home} {hs}-{as_} {away}"},
    "h_kickoff": {"en": "Kickoff: {home} v {away}", "es": "Comienza: {home} vs {away}",
                  "pt": "Começa: {home} x {away}", "fr": "Coup d'envoi : {home} - {away}"},
    # Stories: one sentence on what happened or why, then one on the focus team's chance of winning.
    "c_up": {"en": "{poss} chance of winning rises from {a}% to {b}%.",
             "es": "La probabilidad de victoria de {team} sube del {a}% al {b}%.",
             "pt": "A chance de vitória do {team} sobe de {a}% para {b}%.",
             "fr": "Pour {team}, les chances de victoire passent de {a} % à {b} %."},
    "c_down": {"en": "{poss} chance of winning slips from {a}% to {b}%.",
               "es": "La probabilidad de victoria de {team} baja del {a}% al {b}%.",
               "pt": "A chance de vitória do {team} cai de {a}% para {b}%.",
               "fr": "Pour {team}, les chances de victoire passent de {a} % à {b} %."},
    "c_flat": {"en": "{poss} chance of winning holds at {b}%.",
               "es": "La probabilidad de victoria de {team} se mantiene en el {b}%.",
               "pt": "A chance de vitória do {team} segue em {b}%.",
               "fr": "Pour {team}, les chances de victoire restent à {b} %."},
    "c_up_they": {"en": "Their chance of winning rises from {a}% to {b}%.", "es": "Su probabilidad de victoria sube del {a}% al {b}%.",
                  "pt": "A chance de vitória sobe de {a}% para {b}%.", "fr": "Leurs chances de victoire passent de {a} % à {b} %."},
    "c_down_they": {"en": "Their chance of winning slips from {a}% to {b}%.", "es": "Su probabilidad de victoria baja del {a}% al {b}%.",
                    "pt": "A chance de vitória cai de {a}% para {b}%.", "fr": "Leurs chances de victoire passent de {a} % à {b} %."},
    "c_flat_they": {"en": "Their chance of winning holds at {b}%.", "es": "Su probabilidad de victoria se mantiene en el {b}%.",
                    "pt": "A chance de vitória segue em {b}%.", "fr": "Leurs chances de victoire restent à {b} %."},
    "z_title": {"en": "winning the league", "es": "ganar la liga", "pt": "ser campeão", "fr": "de remporter le titre"},
    "z_top4": {"en": "a top-four finish", "es": "acabar entre los cuatro primeros",
               "pt": "terminar entre os quatro primeiros", "fr": "de finir dans les quatre premiers"},
    "z_relegation": {"en": "relegation", "es": "descender", "pt": "ser rebaixado", "fr": "d'être relégué"},
    "season_moved": {"en": "{poss} chance of {zone} is now {now}%, {dir} from {was}% before kickoff.",
                     "es": "{team} tiene ahora un {now}% de probabilidad de {zone}, frente al {was}% antes del partido.",
                     "pt": "O {team} agora tem {now}% de chance de {zone}, contra {was}% antes do jogo.",
                     "fr": "{team} a désormais {now} % de chances {zone}, contre {was} % avant le match."},
    "season_same": {"en": "{poss} chance of {zone} stays at {now}%.",
                    "es": "{team} sigue con un {now}% de probabilidad de {zone}.",
                    "pt": "O {team} segue com {now}% de chance de {zone}.",
                    "fr": "{team} garde {now} % de chances {zone}."},
    "season_moved_they": {"en": "Their chance of {zone} is now {now}%, {dir} from {was}% before kickoff.",
                          "es": "Ahora tiene un {now}% de probabilidad de {zone}, frente al {was}% antes del partido.",
                          "pt": "Agora tem {now}% de chance de {zone}, contra {was}% antes do jogo.",
                          "fr": "Ils ont désormais {now} % de chances {zone}, contre {was} % avant le match."},
    "season_same_they": {"en": "Their chance of {zone} stays at {now}%.",
                         "es": "Sigue con un {now}% de probabilidad de {zone}.",
                         "pt": "Segue com {now}% de chance de {zone}.",
                         "fr": "Ils gardent {now} % de chances {zone}."},
    "w_goal_now": {"en": "That makes it {home} {hs}, {away} {as_}.", "es": "Con esto, {home} {hs}, {away} {as_}.",
                   "pt": "Com isso, {home} {hs} x {as_} {away}.", "fr": "Le score passe à {hs}-{as_}."},
    "w_red_now": {"en": "{team} will play the rest of the match with ten men.",
                  "es": "{team} jugará con diez el resto del partido.",
                  "pt": "O {team} vai jogar com dez até o fim.", "fr": "{team} va devoir finir le match à dix."},
    "w_goal": {"en": "{team}'s goal is the big reason.", "es": "El gol de {team} es la gran razón.",
               "pt": "O gol do {team} é o grande motivo.", "fr": "Le but de {team} y est pour beaucoup."},
    "w_red": {"en": "{team} being down to ten men is the big reason.",
              "es": "Que {team} juegue con diez es la gran razón.",
              "pt": "O {team} com dez em campo é o grande motivo.", "fr": "{team} à dix, c'est la grande raison."},
    "w_chances": {"en": "The better chances are coming from {team}.",
                  "es": "{team} está generando las mejores ocasiones.",
                  "pt": "O {team} vem criando as melhores chances.", "fr": "{team} se crée les meilleures occasions."},
    "w_clock_level": {"en": "It's level and the minutes are ticking away, so a draw is getting likelier.",
                      "es": "Sigue la igualdad y pasan los minutos, así que el empate es cada vez más probable.",
                      "pt": "Segue empatado e o tempo passa, então o empate fica mais provável.",
                      "fr": "C'est toujours à égalité et le temps file, alors le nul se rapproche."},
    # The draw closing in: the chance of a draw is the number that matters.
    "w_draw_level": {"en": "It's still {hs}-{as_}, and the minutes are ticking away.",
                     "es": "Sigue el {hs}-{as_} y los minutos pasan.",
                     "pt": "Segue {hs} x {as_}, e os minutos passam.",
                     "fr": "C'est toujours {hs}-{as_}, et les minutes filent."},
    "d_up": {"en": "The chance of a draw rises from {a}% to {b}%.",
             "es": "La probabilidad de empate sube del {a}% al {b}%.",
             "pt": "A chance de empate sobe de {a}% para {b}%.",
             "fr": "Les chances de match nul passent de {a} % à {b} %."},
    "d_down": {"en": "The chance of a draw slips from {a}% to {b}%.",
               "es": "La probabilidad de empate baja del {a}% al {b}%.",
               "pt": "A chance de empate cai de {a}% para {b}%.",
               "fr": "Les chances de match nul passent de {a} % à {b} %."},
    "w_clock_behind": {"en": "Time is running out for {team} to find a way back.",
                       "es": "A {team} se le acaba el tiempo para remontar.",
                       "pt": "O tempo está acabando para o {team} buscar a virada.",
                       "fr": "Le temps presse pour {team}, qui doit revenir au score."},
    "w_clock_ahead": {"en": "Every minute that passes brings {team} closer to the win.",
                      "es": "Cada minuto que pasa acerca a {team} a la victoria.",
                      "pt": "Cada minuto que passa deixa o {team} mais perto da vitória.",
                      "fr": "Chaque minute qui passe rapproche {team} de la victoire."},
    "w_kickoff": {"en": "The Gaffer sees a close one.", "es": "El Gaffer espera un partido igualado.",
                  "pt": "O Gaffer espera um jogo equilibrado.", "fr": "Le Gaffer s'attend à un match serré."},
    "w_half": {"en": "There's plenty still to play for in the second half.",
               "es": "Queda mucho por jugar en la segunda parte.",
               "pt": "Ainda tem muito jogo no segundo tempo.", "fr": "Tout reste à jouer en seconde période."},
    "w_quiet": {"en": "A quiet spell, with not much changing.", "es": "Un rato tranquilo, sin grandes cambios.",
                "pt": "Um momento tranquilo, sem grandes mudanças.", "fr": "Un moment calme, sans grand changement."},
    "w_full_win": {"en": "Full time, and it's a {w}-{l} win for {team}.", "es": "Final del partido: {team} gana {w}-{l}.",
                   "pt": "Fim de jogo: o {team} vence por {w} x {l}.", "fr": "C'est terminé, {team} s'impose {w}-{l}."},
    "w_full_draw": {"en": "Full time, and it ends level at {hs}-{as_}.", "es": "Final del partido: empate a {hs}.",
                    "pt": "Fim de jogo: empate em {hs} x {as_}.", "fr": "C'est terminé, match nul {hs}-{as_}."},
    "up": {"en": "Believe! {team} is up to {p}%.", "es": "¡A creer! {team} sube al {p}%.",
           "pt": "Acredite! {team} sobe para {p}%.", "fr": "Y croire ! {team} grimpe à {p} %."},
    # Halftime team talks for each side's fans, by the score at the break.
    "talk_behind": {"en": "Heads up. One half to turn it around, and the Gaffer still gives {team} {p}%. Believe.",
                    "es": "Cabeza alta. Queda un tiempo para darle la vuelta y el Gaffer aún da a {team} un {p}%. A creer.",
                    "pt": "Cabeça erguida. Ainda há um tempo para virar, e o Gaffer dá {p}% ao {team}. Acredite.",
                    "fr": "Tête haute. Il reste une mi-temps pour renverser ça, et le Gaffer donne encore {p} % à {team}. Y croire."},
    "talk_ahead": {"en": "Good half. Stay humble, stay hungry. {team} are at {p}% with 45 to play.",
                   "es": "Buena primera parte. Humildad y hambre. {team} está al {p}% con 45 por jugar.",
                   "pt": "Bom primeiro tempo. Humildade e fome. {team} está com {p}% e 45 minutos pela frente.",
                   "fr": "Belle mi-temps. Humbles et affamés. {team} est à {p} % avec 45 minutes à jouer."},
    "talk_level": {"en": "All square. Cup of tea, deep breath, and go win the second half. {team}: {p}%.",
                   "es": "Todo igualado. Un té, respirar hondo y a ganar la segunda parte. {team}: {p}%.",
                   "pt": "Tudo igual. Um chá, respira fundo e vamos ganhar o segundo tempo. {team}: {p}%.",
                   "fr": "Égalité. Une tasse de thé, on respire, et on gagne la deuxième mi-temps. {team} : {p} %."},
    "down": {"en": "Hold your nerve. {team} still sits at {p}%.", "es": "Calma. {team} sigue con un {p}%.",
             "pt": "Calma. {team} ainda tem {p}%.", "fr": "Gardez la foi. {team} reste à {p} %."},
}


def tr(key: str, lang: str, **kw) -> str:
    return T[key][lang].format(**kw)


def driver_rows(contrib: dict[str, float], window: dict, names: tuple[str, str], focus: int) -> list[dict]:
    """Shapley contributions to labeled, localized driver rows (deltas in points)."""
    rows = []
    for comp, delta in sorted(contrib.items(), key=lambda kv: -abs(kv[1])):
        pts = round(delta * 100)
        if comp == "goals" and window["goals"]:
            g = window["goals"][-1]
            labels = {lang: tr("goal", lang, team=names[g["team"]], min=g["minute"]) for lang in LANGS}
            who = g["team"]
            if len(window["goals"]) > 1:
                labels = {lang: v + f" (+{len(window['goals']) - 1})" for lang, v in labels.items()}
        elif comp == "red_cards" and window["reds"]:
            r = window["reds"][-1]
            labels = {lang: tr("red", lang, team=names[r["team"]], min=r["minute"]) for lang in LANGS}
            who = r["team"]
        elif comp == "chances":
            h, a = window["xg"]
            labels = {lang: tr("chances", lang, h=f"{h:.2f}", a=f"{a:.2f}") for lang in LANGS}
            who = 0 if h >= a else 1
        elif comp == "clock":
            labels = {lang: tr("clock", lang) for lang in LANGS}
            who = None
        else:
            continue
        if pts == 0:
            continue
        rows.append({"component": comp, "delta": pts, "label": labels, "team": who})
    return rows


def possessive(name: str) -> str:
    return f"{name}'" if name.endswith("s") else f"{name}'s"


def _story(lang: str, *, trigger: str, names: tuple[str, str], score: tuple[int, int], focus: int, a: int, b: int,
           drivers: list[dict], red_team: int | None, var: dict | None, draw: tuple[int, int] | None = None) -> str:
    """Two plain sentences: what happened (or why the chances moved), then the focus team's chance of winning
    (or, when the draw is closing in, the chance of a draw)."""
    team = names[focus]
    who = {"team": team, "poss": possessive(team)}
    if trigger == "swing_draw" and draw:
        hs, as_ = score
        first = (tr("w_draw_level", lang, hs=hs, as_=as_) if hs == as_ else
                 tr("w_clock_behind" if (score[focus] < score[1 - focus]) else "w_clock_ahead", lang, team=team))
        return f"{first} {tr('d_up', lang, a=draw[0], b=draw[1])}"
    if trigger == "var_overturned" and var:
        return tr("var_story", lang, reason=tr(f"r_{var['reason']}", lang), b=b, s=var["stands_pct"],
                  player=var.get("player") or team, **who)
    if trigger == "full_time":
        hs, as_ = score
        if hs == as_:
            return tr("w_full_draw", lang, hs=hs, as_=as_)
        win = 0 if hs > as_ else 1
        return tr("w_full_win", lang, team=names[win], w=max(hs, as_), l=min(hs, as_))
    top = next((d for d in drivers if abs(d["delta"]) >= 1), None)
    mine, theirs = (score[0], score[1]) if focus == 0 else (score[1], score[0])
    if trigger == "goal":
        first = tr("w_goal_now", lang, home=names[0], away=names[1], hs=score[0], as_=score[1])
    elif trigger == "red_card":
        first = tr("w_red_now", lang, team=names[red_team if red_team is not None else focus])
    elif trigger == "kickoff":
        first = tr("w_kickoff", lang)
    elif top and top["component"] == "clock" and mine == theirs and draw and draw[1] > draw[0]:
        # Level, and the clock is the story: the draw is the thing getting likelier, so its chance is the
        # number to give ("a draw is getting likelier" next to a team's rising chance made no sense).
        return f"{tr('w_clock_level', lang)} {tr('d_up', lang, a=draw[0], b=draw[1])}"
    elif top and top["component"] == "clock" and mine != theirs:
        first = tr("w_clock_behind" if mine < theirs else "w_clock_ahead", lang, team=team)
    elif (top := next((d for d in drivers if abs(d["delta"]) >= 1 and d["component"] != "clock"), None)) \
            and top["component"] in ("goals", "red_cards", "chances") and top.get("team") is not None:
        key = {"goals": "w_goal", "red_cards": "w_red", "chances": "w_chances"}[top["component"]]
        first = tr(key, lang, team=names[top["team"]])
    elif trigger == "half_time":
        first = tr("w_half", lang)
    else:
        first = tr("w_quiet", lang)
    change = "c_flat" if a == b else "c_up" if b > a else "c_down"
    if team in first and names[1 - focus] not in first:
        change += "_they"  # the first sentence named them: "Their chance of winning..."
    return f"{first} {tr(change, lang, a=a, b=b, **who)}"


def season_sentence(lang: str, season: dict, they: bool = False) -> str:
    """What the final result did to the season: "Eastholme Rangers' chance of a top-four finish is now 12%..."."""
    zone = tr(f"z_{season['zone']}", lang)
    now, was = season["now_pct"], season["was_pct"]
    who = {"team": season["club"], "poss": possessive(season["club"]), "zone": zone, "now": now, "was": was}
    suffix = "_they" if they else ""
    if now == was:
        return tr(f"season_same{suffix}", lang, **who)
    return tr(f"season_moved{suffix}", lang, dir="up" if now > was else "down", **who)


def template_package(*, trigger: str, names: tuple[str, str], score: tuple[int, int], minute: int,
                     before: dict, after: dict, focus: int, drivers: list[dict], scorer: str | None,
                     red_team: int | None, stats: dict, var: dict | None = None,
                     season: dict | None = None) -> dict:
    side = "home" if focus == 0 else "away"
    a, b = round(before[side] * 100), round(after[side] * 100)
    team = names[focus]
    fmt = {"home": names[0], "away": names[1], "hs": score[0], "as_": score[1], "min": minute}
    headline = {}
    for lang in LANGS:
        if trigger == "goal":
            key = "h_goal_var" if var and var.get("stood") else "h_goal"
            headline[lang] = tr(key, lang, player=scorer or team, team=team)
        elif trigger == "var_overturned" and var:
            headline[lang] = tr("h_var_out", lang, player=var["player"].split()[-1])
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
    draw = (round(before["draw"] * 100), round(after["draw"] * 100))
    story = {lang: _story(lang, trigger=trigger, names=names, score=score, focus=focus, a=a, b=b,
                          drivers=drivers, red_team=red_team, var=var, draw=draw) for lang in LANGS}
    if trigger == "full_time" and season:
        # "Their" when the first sentence just named the club (the winner).
        they = score[0] != score[1] and season.get("team") == (0 if score[0] > score[1] else 1)
        story = {lang: f"{story[lang]} {season_sentence(lang, season, they)}" for lang in LANGS}
    club_lines = {}
    for i, key in ((0, "home"), (1, "away")):
        p_now = round(after["home" if i == 0 else "away"] * 100)
        p_was = round(before["home" if i == 0 else "away"] * 100)
        if trigger == "half_time":
            mine, theirs = (score[0], score[1]) if i == 0 else (score[1], score[0])
            key_t = "talk_behind" if mine < theirs else "talk_ahead" if mine > theirs else "talk_level"
            club_lines[key] = {lang: tr(key_t, lang, team=names[i], p=p_now) for lang in LANGS}
        else:
            club_lines[key] = {lang: tr("up" if p_now >= p_was else "down", lang, team=names[i], p=p_now)
                               for lang in LANGS}
    h, aw = stats["teams"]
    analyst = {}
    for lang in LANGS:
        drv = ", ".join(f"{d['label'][lang]} {d['delta']:+d}" for d in drivers) or tr("no_change", lang)
        analyst[lang] = tr("analyst", lang, hx=f"{h['xg']:.2f}", ax=f"{aw['xg']:.2f}", hs=h["shots"], as_=aw["shots"],
                           hp=h["possession"], ap=aw["possession"], ht=h["field_tilt"], at=aw["field_tilt"],
                           team=team, drivers=drv)
    return {"headline": headline, "story": story, "analyst": analyst, "club_lines": club_lines,
            "source": "template"}


# ---------------------------------------------------------------- events read aloud
EV = {
    "goal": {"en": "goal for {team}! {player} scores, and it's {hs}-{as_}.",
             "es": "¡gol de {team}! Marca {player} y se pone {hs}-{as_}.",
             "pt": "gol do {team}! {player} marca, e está {hs}-{as_}.",
             "fr": "but pour {team} ! {player} marque, {hs}-{as_}."},
    "saved": {"en": "a chance for {player} of {team}, saved.", "es": "ocasión de {player}, de {team}, y el portero la para.",
              "pt": "chance de {player}, do {team}, e o goleiro defende.", "fr": "occasion pour {player}, de {team}, arrêtée par le gardien."},
    "off": {"en": "a chance for {player} of {team}, off target.", "es": "ocasión de {player}, de {team}, que se va fuera.",
            "pt": "chance de {player}, do {team}, para fora.", "fr": "occasion pour {player}, de {team}, non cadrée."},
    "red_card": {"en": "a red card for {player} of {team}.", "es": "tarjeta roja para {player}, de {team}.",
                 "pt": "cartão vermelho para {player}, do {team}.", "fr": "carton rouge pour {player}, de {team}."},
    "yellow_card": {"en": "a yellow card for {player} of {team}.", "es": "tarjeta amarilla para {player}, de {team}.",
                    "pt": "cartão amarelo para {player}, do {team}.", "fr": "carton jaune pour {player}, de {team}."},
    "substitution": {"en": "a change for {team}: {player} comes on for {off}.", "es": "cambio en {team}: entra {player} por {off}.",
                     "pt": "substituição no {team}: entra {player}, sai {off}.", "fr": "changement pour {team} : {player} remplace {off}."},
    "half_time": {"en": "Halftime. {home} {hs}, {away} {as_}.", "es": "Descanso. {home} {hs}, {away} {as_}.",
                  "pt": "Intervalo. {home} {hs}, {away} {as_}.", "fr": "Mi-temps. {home} {hs}, {away} {as_}."},
    "full_time": {"en": "Full time. {home} {hs}, {away} {as_}.", "es": "Final del partido. {home} {hs}, {away} {as_}.",
                  "pt": "Fim de jogo. {home} {hs}, {away} {as_}.", "fr": "Fin du match. {home} {hs}, {away} {as_}."},
    "var_check": {"en": "VAR is checking {player}'s goal for {team} for {reason}.",
                  "es": "el VAR revisa el gol de {player}, de {team}, por {reason}.",
                  "pt": "o VAR checa o gol de {player}, do {team}, por {reason}.",
                  "fr": "la VAR vérifie le but de {player}, de {team}, pour {reason}."},
    "var_stands": {"en": "VAR says {player}'s goal for {team} stands.", "es": "el VAR da por bueno el gol de {player}, de {team}.",
                   "pt": "o VAR confirma o gol de {player}, do {team}.", "fr": "la VAR valide le but de {player}, de {team}."},
    "var_out": {"en": "VAR rules out {player}'s goal for {team} for {reason}.",
                "es": "el VAR anula el gol de {player}, de {team}, por {reason}.",
                "pt": "o VAR anula o gol de {player}, do {team}, por {reason}.",
                "fr": "la VAR refuse le but de {player}, de {team}, pour {reason}."},
}


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _at_minute(n: int, lang: str) -> str:
    return {"en": f"In the {_ordinal(n)} minute, ", "es": f"Minuto {n}: ", "pt": f"Aos {n} minutos, ",
            "fr": f"À la {n}{'re' if n == 1 else 'e'} minute, "}[lang]


def event_spoken(item: dict, names: tuple[str, str], lang: str) -> str:
    """One match event as a sentence to read aloud: "In the 23rd minute, a chance for Kofi Lorford of
    Eastholme Rangers, saved." No xG or other figures a listener would have to decode."""
    et = item.get("type")
    key = ("saved" if item.get("on") else "off") if et == "shot" else \
        ("var_stands" if item.get("decision") == "stands" else "var_out") if et == "var_decision" else et
    if key not in EV:
        return ""
    t = item.get("team")
    hs, as_ = (item.get("score") or [0, 0])[:2]
    reason = item.get("reason") or "offside"
    text = EV[key][lang].format(team=names[t] if t in (0, 1) else "", player=item.get("player") or "",
                                off=item.get("off") or "", hs=hs, as_=as_, home=names[0], away=names[1],
                                reason=tr(f"r_{reason}", lang) if f"r_{reason}" in T else reason)
    if lang == "fr":  # "le but de Ivan" -> "le but d'Ivan"
        text = re.sub(r"\b([Dd])e ([AEIOUÉÈ])", r"\1'\2", text)
    if et in ("half_time", "full_time"):
        return text
    prefix = _at_minute(int(item.get("minute") or 0), lang)
    if prefix.endswith(": "):  # "Minuto 14: ¡Gol de..." starts a new phrase
        text = text[:1].upper() + text[1:] if not text.startswith("¡") else "¡" + text[1:2].upper() + text[2:]
    return prefix + text
