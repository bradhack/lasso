"""Stickers: achievements for your sticker book, in four languages.

Each sticker is earned once (repeat wins add to its count). Tiers follow how hard it is to get:
bronze for getting started, silver for skill, gold for the great days.
"""

from __future__ import annotations

STICKERS: dict[str, dict] = {
    "first_call": {"tier": "bronze",
                   "name": {"en": "First Call", "es": "Primera apuesta", "pt": "Primeiro palpite", "fr": "Premier prono"},
                   "how": {"en": "Make your first call", "es": "Haz tu primer pronóstico",
                           "pt": "Faça seu primeiro palpite", "fr": "Fais ton premier prono"}},
    "called_it": {"tier": "bronze",
                  "name": {"en": "Called It", "es": "Lo sabía", "pt": "Eu avisei", "fr": "Je l'avais dit"},
                  "how": {"en": "Win your first call", "es": "Acierta tu primer pronóstico",
                          "pt": "Acerte seu primeiro palpite", "fr": "Gagne ton premier prono"}},
    "believe": {"tier": "bronze",
                "name": {"en": "Believe", "es": "Creer", "pt": "Acreditar", "fr": "Y croire"},
                "how": {"en": "Touch the sign, or back a comeback, for a team that's behind",
                        "es": "Toca el cartel, o apuesta por la remontada, de quien va perdiendo",
                        "pt": "Toque na placa, ou aposte na virada, de quem está perdendo",
                        "fr": "Touche le panneau, ou crois au retour, d'une équipe menée"}},
    "halftime_tea": {"tier": "bronze",
                     "name": {"en": "Halftime Tea", "es": "Té del descanso", "pt": "Chá do intervalo", "fr": "Thé de la mi-temps"},
                     "how": {"en": "Stick around for the halftime story", "es": "Quédate para la historia del descanso",
                             "pt": "Fique para a história do intervalo", "fr": "Reste pour le récit de la mi-temps"}},
    "polyglot": {"tier": "bronze",
                 "name": {"en": "Polyglot", "es": "Políglota", "pt": "Poliglota", "fr": "Polyglotte"},
                 "how": {"en": "Read stories in two languages", "es": "Lee historias en dos idiomas",
                         "pt": "Leia histórias em dois idiomas", "fr": "Lis des récits en deux langues"}},
    "underdog": {"tier": "silver",
                 "name": {"en": "Underdog Whisperer", "es": "Amigo del débil", "pt": "Amigo do azarão", "fr": "Ami des outsiders"},
                 "how": {"en": "Win a call the Gaffer gave under 25%", "es": "Acierta algo que el Gaffer veía por debajo del 25%",
                         "pt": "Acerte algo que o Gaffer via abaixo de 25%", "fr": "Gagne un prono que le Gaffer voyait sous 25 %"}},
    "hat_trick": {"tier": "silver",
                  "name": {"en": "Hat-trick", "es": "Triplete", "pt": "Hat-trick", "fr": "Coup du chapeau"},
                  "how": {"en": "Three right in a row in one match", "es": "Tres aciertos seguidos en un partido",
                          "pt": "Três acertos seguidos em um jogo", "fr": "Trois bons pronos de suite dans un match"}},
    "on_fire": {"tier": "silver",
                "name": {"en": "On Fire", "es": "En racha", "pt": "Pegando fogo", "fr": "En feu"},
                "how": {"en": "Reach a streak of 5", "es": "Llega a una racha de 5", "pt": "Chegue a uma sequência de 5",
                        "fr": "Atteins une série de 5"}},
    "rom_com": {"tier": "silver",
                "name": {"en": "Rom-Com Ending", "es": "Final de película", "pt": "Final de novela", "fr": "Fin de comédie romantique"},
                "how": {"en": "Call a goal in the last 10 minutes", "es": "Acierta un gol en los últimos 10 minutos",
                        "pt": "Acerte um gol nos últimos 10 minutos", "fr": "Annonce un but dans les 10 dernières minutes"}},
    "goldfish": {"tier": "silver",
                 "name": {"en": "Goldfish Recovery", "es": "Memoria de pez", "pt": "Memória de peixinho", "fr": "Mémoire de poisson rouge"},
                 "how": {"en": "Use your Goldfish, then win your next call", "es": "Usa tu Goldfish y acierta el siguiente",
                         "pt": "Use seu Goldfish e acerte o próximo", "fr": "Utilise ton Goldfish puis gagne le prono suivant"}},
    "sharp_eye": {"tier": "silver",
                  "name": {"en": "Sharp Eye", "es": "Ojo clínico", "pt": "Olho clínico", "fr": "Œil de lynx"},
                  "how": {"en": "Win 10 calls", "es": "Acierta 10 pronósticos", "pt": "Acerte 10 palpites", "fr": "Gagne 10 pronos"}},
    "long_shot": {"tier": "gold",
                  "name": {"en": "Long Shot", "es": "Golpe de suerte", "pt": "Zebra", "fr": "Coup de poker"},
                  "how": {"en": "Win a call the Gaffer gave under 10%", "es": "Acierta algo que el Gaffer veía por debajo del 10%",
                          "pt": "Acerte algo que o Gaffer via abaixo de 10%", "fr": "Gagne un prono que le Gaffer voyait sous 10 %"}},
    "ten_men": {"tier": "gold",
                "name": {"en": "Ten Men", "es": "Con diez", "pt": "Com dez", "fr": "À dix"},
                "how": {"en": "Call a goal by a team down to ten men", "es": "Acierta un gol de un equipo con diez",
                        "pt": "Acerte um gol de um time com dez", "fr": "Annonce un but d'une équipe réduite à dix"}},
    "comeback": {"tier": "gold",
                 "name": {"en": "Comeback Believer", "es": "Creyente de la remontada", "pt": "Crente da virada", "fr": "Croyant de la remontada"},
                 "how": {"en": "Back a comeback, and see it happen", "es": "Apuesta por la remontada y que se cumpla",
                         "pt": "Aposte na virada e veja acontecer", "fr": "Crois au retour et vois-le arriver"}},
    "bullseye": {"tier": "gold",
                 "name": {"en": "Bullseye", "es": "En el blanco", "pt": "Na mosca", "fr": "Dans le mille"},
                 "how": {"en": "Call the final result in the first 10 minutes", "es": "Acierta el resultado final en los primeros 10 minutos",
                         "pt": "Acerte o resultado final nos primeiros 10 minutos", "fr": "Trouve le résultat final dans les 10 premières minutes"}},
    "unstoppable": {"tier": "gold",
                    "name": {"en": "Unstoppable", "es": "Imparable", "pt": "Imparável", "fr": "Inarrêtable"},
                    "how": {"en": "Reach a streak of 10", "es": "Llega a una racha de 10", "pt": "Chegue a uma sequência de 10",
                            "fr": "Atteins une série de 10"}},
    "diamond_dog": {"tier": "gold",
                    "name": {"en": "Diamond Dog", "es": "Diamond Dog", "pt": "Diamond Dog", "fr": "Diamond Dog"},
                    "how": {"en": "Top the Diamond Dogs league", "es": "Lidera la liga Diamond Dogs",
                            "pt": "Lidere a liga Diamond Dogs", "fr": "Prends la tête de la ligue Diamond Dogs"}},
}


def public_stickers(u: dict) -> list[dict]:
    """The whole sticker book in catalog order, earned or not, so the app can show what is left to collect."""
    mine = u.get("stickers") or {}
    return [{"id": k, "tier": v["tier"], "name": v["name"], "how": v["how"],
             "earned": k in mine, "count": mine.get(k, {}).get("count", 0),
             "detail": mine.get(k, {}).get("detail")} for k, v in STICKERS.items()]


def award(u: dict, key: str, detail: str | None = None, ts: float = 0.0) -> dict | None:
    """Record a sticker. Returns a message for the first time it is earned, None on repeats."""
    book = u.setdefault("stickers", {})
    if key in book:
        book[key]["count"] = book[key].get("count", 1) + 1
        return None
    book[key] = {"count": 1, "earned_at": ts, "detail": detail}
    s = STICKERS[key]
    return {"type": "sticker", "sticker": {"id": key, "tier": s["tier"], "name": s["name"], "how": s["how"],
                                           "detail": detail}}
