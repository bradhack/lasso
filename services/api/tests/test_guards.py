"""The code checks every agent answer and story passes before a fan sees it.

Each case is a real slip from an evaluation run on the live app (docs/agent-eval.md), replayed here against the
showcase match at the minute it happened. No cloud needed: the match is replayed in-process from the demo data.
"""

import asyncio
import copy

import pytest

from lasso_api import feed as F
from lasso_api import main as M
from lasso_api import narrative as N
from lasso_api.matchroom import MatchRoom

SHOWCASE = next(iter(F.SHOWCASE_VAR))
NAMES = ("Eastholme Rangers", "Brackenford City")


MINUTES = (7, 18, 24, 26, 36, 40, 54, 89)  # the minutes the slips below happened at
_rooms: dict = {}


def _replay() -> None:
    """Play the showcase match once, in-process, keeping a copy of the room at each minute above."""
    room = MatchRoom(SHOWCASE, M.data)
    wanted = sorted(MINUTES)

    async def on_event(_target: str, ev: dict) -> None:
        if ev.get("type") == "match_reset":
            room.reset()
            return
        room.ingest(ev)
        while wanted and room.minute() >= wanted[0]:
            _rooms[wanted.pop(0)] = copy.deepcopy(room)

    F.VAR_MIN_SECONDS = 0
    asyncio.run(F.replay(M.data, SHOWCASE, on_event, 0.0))
    _rooms[None] = room


def room_at(minute: int | None) -> MatchRoom:
    if not _rooms:
        _replay()
    return _rooms[minute]


def test_showcase_replays():
    room = room_at(None)
    assert room.status == "finished" and list(room.state.goals) == [2, 1]
    assert tuple(room.names) == NAMES


# ---------------------------------------------------------------- neutral: the Gaffer watched, it didn't play

@pytest.mark.parametrize("lang,text", [
    ("es", "Ganamos con diez porque aguantamos y conseguimos el segundo gol al 82', y el tiempo jugó a nuestro favor. "
           "En el 87' Eastholme tienen 89% de ganar y el empate 9%."),
    ("es", "Gané con diez porque aguanté atrás y pillé el gol decisivo en el 82'. Tras la roja al 5', Eastholme "
           "tuvieron un 89% de opciones de ganar ahora y están más cerca de cerrar el partido."),
    ("en", "We held on with ten. Eastholme Rangers lead 2-1 and have an 89% chance of winning with three minutes left."),
])
def test_neutral_drops_taking_a_side(lang, text):
    out = M._neutral(text, lang)
    assert out and "anamos" not in out and "Gané" not in out and "We " not in out
    assert "89%" in out


def test_neutral_keeps_a_neutral_answer():
    text = "Eastholme Rangers won with ten because they held firm and Adam Penke scored at 82'."
    assert M._neutral(text, "en") == text


# ---------------------------------------------------------------- facts that must match the match

def test_more_shots_for_the_side_with_fewer_is_dropped():
    room = room_at(26)
    text = ("Brackenford City está jogando melhor neste momento. Têm 77% de posse, mais chutes e controlo do jogo, "
            "e a sua hipótese de vencer é 45%. Eastholme, com um jogador a menos desde o 5', soma 0,59 xG contra 0,18.")
    out = M._wrong_shots(text, room, "pt")
    assert "mais chutes" not in out and "0,59 xG" in out


def test_leads_the_shots_in_french_is_dropped():
    room = room_at(40)
    text = ("Brackenford City est le plus probable pour marquer le prochain but, 46 % contre 31 % pour Eastholme. "
            "Brackenford contrôle le jeu avec 69 % de possession et mène les frappes longues.")
    out = M._wrong_shots(text, room, "fr")
    assert "frappes" not in out and "46 %" in out


def test_more_shots_stub_is_completed_with_the_chances():
    room = room_at(26)
    text = "Brackenford City está jogando melhor neste momento. Têm 77% de posse, mais chutes (2 contra 5)."
    out = M._wrong_shots(text, room, "pt")
    assert "mais chutes" not in out and out.startswith("Brackenford City está jogando melhor") and "empate" in out


@pytest.mark.parametrize("minute,lang,text,wrong", [
    (36, "es", "Sí, Eastholme puede remontar; están 1-1 a los 36' pero con diez hombres, y tienen un 24% de ganar. "
               "Brackenford es favorito con 41%, y Eastholme son más probables para el próximo gol con 32%.",
     "más probables"),
    (26, "pt", "Brackenford City está jogando melhor agora. Têm 77% de posse contra 23% e maiores chances de ganhar, "
               "45% a 24%. Ainda assim, Eastholme Rangers têm 0,59 de xG contra 0,18 e uma chance maior de marcar o "
               "próximo gol, 34% a 51% a favor do Brackenford.", "chance maior"),
])
def test_wrong_club_likelier_to_score_next_is_dropped(minute, lang, text, wrong):
    out = M._next_goal_side(text, room_at(minute), lang)
    assert wrong not in out and len(out.split()) >= 8


def test_right_club_likelier_to_score_next_stays():
    text = "Eastholme Rangers have a 34% chance to score next, while Brackenford City are likelier to score next at 52%."
    assert M._next_goal_side(text, room_at(24), "en") == text


def test_wrong_leader_is_replaced_by_the_chances():
    room = room_at(89)
    text = ("Oui, il fallait y croire. À la 89e Brackenford City mène encore 2-1 et a moins de 1% de chances, mais le "
            "match n'est pas fini.")
    out = M._wrong_leader(text, room, "fr", complete=True)
    assert "mène encore" not in out and out.startswith("Oui, il fallait y croire.") and "En ce moment" in out


def test_wrong_team_pct_is_dropped():
    room = room_at(7)
    text = ("Brackenford lead 1-0 after the red card. Eastholme Rangers have a 77% chance of winning now. "
            "Brackenford City are likelier to score next, 56% to Eastholme's 34%.")
    out = M._wrong_team_pct(text, room, "en")
    assert "Eastholme Rangers have a 77%" not in out


def test_rise_cannot_end_below_its_size():
    text = "The red card pushed Brackenford City's win chance up by 25 points to Brackenford's 24%."
    assert M._rise_consistent(text) == "The red card pushed Brackenford City's win chance up by 25 points."
    ok = "The red card pushed Brackenford City up by 26 points to 77%."
    assert M._rise_consistent(ok) == ok


def test_first_name_alone_gets_the_full_name():
    room = room_at(18)
    out = M._full_names("Cambiaron por la roja a Kofi en el 5'. Kofi Lorford se fue.", room)
    assert out == "Cambiaron por la roja a Kofi Lorford en el 5'. Kofi Lorford se fue."


def test_guessed_tactic_after_not_tracking_is_cut():
    text = ("I don't track formations. From the match though: Eastholme are a man down since the 5th minute and "
            "Brackenford have dominated possession (77% to 23%), so Eastholme look compact and defensive while "
            "Brackenford press on, Eastholme 0.55 xG, Brackenford 0.16 xG.")
    out = M._no_guessed_tactics(text)
    assert "compact" not in out and "0.55 xG" in out


def test_talk_about_sources_is_dropped():
    room = room_at(54)
    text = ("Eastholme Rangers lead on total xG, 0.68 to Brackenford City's 0.30, because Eastholme have created more "
            "shots. The match notes a shift toward Brackenford for future chances.")
    out = M._no_meta(text, room, "en")
    assert "notes" not in out and "0.68" in out


@pytest.mark.parametrize("lang,text,want", [
    ("en", "Brackenford have a 0% chance.", "less than a 1% chance"),
    ("es", "Brackenford tiene el 0% de ganar.", "menos del 1%"),
    ("pt", "Brackenford tem 0% de chance.", "menos de 1%"),
    ("fr", "Brackenford a 0 % de chances.", "moins de 1 %"),
    ("en", "Eastholme have a 100% chance.", "more than a 99% chance"),
])
def test_nothing_is_certain_while_live(lang, text, want):
    assert want in M._not_certain(text, lang)


def test_ten_and_half_percent_are_left_alone():
    assert M._not_certain("10% and 0.5% and 20%", "en") == "10% and 0.5% and 20%"


def test_no_final_chances_after_full_time():
    out = M._no_final_chances("Eastholme won 2-1. They had a 100% chance of winning at the end. Penke scored at 82'.")
    assert "100%" not in out


def test_trailing_question_goes_to_the_chips():
    text = "Adam Penke scored the winner at 82', and it stood after VAR. Want me to explain the red card?"
    assert M._no_trailing_questions(text) == "Adam Penke scored the winner at 82', and it stood after VAR."


def test_fans_get_no_xg_decimals():
    out = M._plain_for_fans("Eastholme lead the chances, with 0.68 xG to 0.30. They have a 21% chance of winning now.")
    assert "0.68" not in out and "21%" in out


def test_real_clubs_never_appear():
    assert M._no_real_clubs("Arsenal did this once. It is 1-1.") == ""
    text = "Eastholme Rangers and Brackenford City are level at 1-1 with the draw at 39%."
    assert M._no_real_clubs(text) == text


def test_next_goal_names_the_likelier_side_first():
    out = M._next_goal_consistent("Eastholme are likelier to score next, 38% to Brackenford's 53%.")
    assert out == "Brackenford are likelier to score next, 53% to Eastholme's 38%."


# ---------------------------------------------------------------- translations and house style

@pytest.mark.parametrize("lang,text,want", [
    ("pt", "Eastholme está a controlar o jogo e marcou dois golos na primeira parte.", "controlando"),
    ("pt", "Eastholme está a controlar o jogo e marcou dois golos na primeira parte.", "gols no primeiro tempo"),
    ("pt", "Têm mais controlo do jogo e a sua hipótese de vencer é 45%.", "controle do jogo e a sua chance"),
    ("pt", "Agora, ao minuto 58, o empate tem 48%.", "aos 58 minutos"),
    ("es", "Aún así, Eastholme puede remontar.", "Aun así"),
    ("fr", "Brackenford a 24 % de marquer le prochain, Eastholme 17 %.", "le prochain but"),
    ("fr", "Brackenford a moins de 1 % selon les chiffres affichés.", "moins de 1 %."),
    ("en", "Brackenford lead 0-1 and are the favourites.", "lead 1-0 and are the favorites"),
    ("en", "It was a early red card and a 8% chance.", "an early red card and an 8% chance"),
    ("es", "Eastholme tiene una 24% chance.", "un 24% opción"),
])
def test_localize_fixes(lang, text, want):
    assert want in M._localize(lang, text)


def test_portuguese_decimals_use_commas():
    assert "0,59 xG" in M._localize("pt", "Eastholme soma 0.59 xG.")


# ---------------------------------------------------------------- instant stories name the player

@pytest.mark.parametrize("lang", ["en", "es", "pt", "fr"])
def test_instant_stories_name_the_player(lang):
    kw = dict(names=NAMES, focus=0, a=10, b=24, drivers=[], red_team=None, var=None)
    goal = N._story(lang, trigger="goal", score=(1, 1), player="Reuben Belwell", **kw)
    red = N._story(lang, trigger="red_card", score=(0, 1), player="Kofi Lorford", **{**kw, "red_team": 0})
    var = N._story(lang, trigger="var_overturned", score=(0, 1), **{
        **kw, "var": {"reason": "offside", "player": "Victor Yarola", "stands_pct": 23}})
    assert "Reuben Belwell" in goal and "Kofi Lorford" in red and "Victor Yarola" in var


def test_showcase_moments_name_their_players():
    room = room_at(None)
    named = {m["trigger"]: m["story"]["en"] for m in room.moments if m["trigger"] in ("red_card", "var_overturned")}
    assert "Kofi Lorford" in named["red_card"] and "Victor Yarola" in named["var_overturned"]


# ---------------------------------------------------------------- Listen reads exactly what's on screen

def test_fingerprint_is_stable_and_text_sensitive():
    a = M.text_fingerprint("Adam Penke scores in the 82nd minute.")
    assert a == M.text_fingerprint("Adam Penke scores in the 82nd minute.")
    assert a != M.text_fingerprint("Adam Penke scores in the 83rd minute.")
