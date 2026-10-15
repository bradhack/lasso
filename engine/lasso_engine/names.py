"""Fictional club and player identities for the Lasso synthetic league.

Every club, place and player here is invented. Names are generated from
common given names and synthetic surnames so that no real footballer or
club is represented.
"""

from __future__ import annotations

import numpy as np

# (name, short code, monogram, primary color, secondary color)
CLUBS: list[tuple[str, str, str, str, str]] = [
    ("Harbourside Rovers", "HBR", "HR", "#D3D7DE", "#1A3A5C"),
    ("Kingsmere Athletic", "KMA", "KA", "#7A1F2B", "#E6DEEA"),
    ("Wexley United", "WXU", "WU", "#C8102E", "#F2F2F2"),
    ("Brackenford City", "BKC", "BC", "#5BA3D9", "#FFFFFF"),
    ("Saltmarsh Town", "SMT", "ST", "#E0A526", "#1C1C1C"),
    ("Hollowell Wanderers", "HLW", "HW", "#2E6B3A", "#F4E9C8"),
    ("Northwick Forest", "NWF", "NF", "#1F5130", "#D8B26E"),
    ("Calder Mills", "CDM", "CM", "#6B4F78", "#F4F1F6"),
    ("Eastholme Rangers", "EHR", "ER", "#0E4C92", "#F5C400"),
    ("Stormhaven", "STH", "SH", "#3B4A57", "#9FD3E6"),
    ("Ravensgate Albion", "RVA", "RA", "#111111", "#D3D7DE"),
    ("Millbrook Harriers", "MBH", "MH", "#E35205", "#101820"),
    ("Larkspur Park", "LKP", "LP", "#8F7BC6", "#FFFFFF"),
    ("Fenwick Borough", "FWB", "FB", "#A3262A", "#0B2240"),
    ("Oakhurst United", "OKU", "OU", "#4E7D2F", "#FFFFFF"),
    ("Silverlea", "SVL", "SL", "#A7AEB6", "#232A33"),
    ("Westmarch", "WSM", "WM", "#7C2D12", "#FDE68A"),
    ("Cindervale", "CDV", "CV", "#3F3F46", "#F97316"),
    ("Highmoor Athletic", "HMA", "HA", "#155E75", "#ECFEFF"),
    ("Port Elsworth", "PEW", "PE", "#1E3A8A", "#FCA5A5"),
]

GIVEN_NAMES = [
    "Aaron", "Adam", "Adrian", "Alex", "Amadou", "Andre", "Anton", "Arlo", "Ben", "Bruno",
    "Caleb", "Callum", "Carlos", "Cian", "Dario", "Declan", "Diego", "Elias", "Emil", "Enzo",
    "Ethan", "Felix", "Finn", "Gabriel", "Hugo", "Ibrahim", "Isaac", "Ivan", "Jakob", "Jamal",
    "Javier", "Jonas", "Jude", "Kai", "Kofi", "Kwame", "Lars", "Leo", "Liam", "Luca",
    "Lucas", "Malik", "Marco", "Mateo", "Max", "Milan", "Moussa", "Nico", "Noah", "Oisin",
    "Oliver", "Omar", "Oscar", "Owen", "Pablo", "Rafael", "Reuben", "Rhys", "Rory", "Sami",
    "Santiago", "Sean", "Silas", "Tariq", "Theo", "Tomas", "Ty", "Victor", "Wes", "Yusuf",
]

_SURNAME_HEADS = [
    "Ash", "Brook", "Cal", "Dun", "El", "Fen", "Gar", "Hol", "Kir", "Lang", "Mar", "Nor",
    "Ock", "Pen", "Quar", "Rad", "Sel", "Thorn", "Ul", "Vel", "Wren", "Yar", "Bel", "Cor",
    "Dal", "Esk", "Fal", "Hal", "Ives", "Lor", "Mor", "Ost", "Rav", "Stan", "Tal", "Var",
]
_SURNAME_TAILS = [
    "by", "ford", "ley", "more", "ton", "wick", "well", "ham", "den", "stead", "worth",
    "ard", "ani", "ez", "ini", "son", "eau", "ov", "ssen", "ke", "ola", "aga", "ero", "ane",
]


def surname(rng: np.random.Generator) -> str:
    return str(rng.choice(_SURNAME_HEADS)) + str(rng.choice(_SURNAME_TAILS))


def player_name(rng: np.random.Generator, used: set[str]) -> str:
    for _ in range(1000):
        name = f"{rng.choice(GIVEN_NAMES)} {surname(rng)}"
        if name not in used:
            used.add(name)
            return name
    raise RuntimeError("ran out of unique player names")
