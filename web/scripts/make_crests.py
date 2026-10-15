"""Generate Lasso's 20 original club crests as SVG (web/src/crests/<club_id>.svg).

Every crest shares one system so the league feels designed as a set: a distinct
silhouette per club, filled with the club's primary color, a thin rim, an inset
keyline, and one bold emblem in the club's secondary color. All clubs and crests
are fictional. Run from the repo root:

    python web/scripts/make_crests.py
"""

from __future__ import annotations

import math
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "src" / "crests"

# ------------------------------------------------------------------ silhouettes (100 x 100 box)
SHAPES = {
    "heater": "M14 8H86V44C86 70 68 86 50 95C32 86 14 70 14 44Z",
    "roundel": "M50 4A46 46 0 1 1 49.99 4Z",
    "round_base": "M13 8H87V54A37 37 0 0 1 13 54Z",
    "kite": "M50 4C64 4 78 8 88 13V48C88 71 69 87 50 96C31 87 12 71 12 48V13C22 8 36 4 50 4Z",
    "octagon": "M31 5H69L95 31V69L69 95H31L5 69V31Z",
    "oval": "M50 3C73 3 88 24 88 50C88 76 73 97 50 97C27 97 12 76 12 50C12 24 27 3 50 3Z",
    "hex_point": "M50 3L91 26.5V73.5L50 97L9 73.5V26.5Z",
    "hex_flat": "M27 7H73L97 50L73 93H27L3 50Z",
    "ogee": "M11 9H89V58C89 76 74 86 63 89C56 91 52 93 50 97C48 93 44 91 37 89C26 86 11 76 11 58Z",
    "diamond": "M50 2L98 50L50 98L2 50Z",
    "castle": "M12 20H22V9H34V20H44V9H56V20H66V9H78V20H88V54C88 74 70 88 50 96C30 88 12 74 12 54Z",
    "banner": "M15 4H85V93L50 77L15 93Z",
    "arch": "M16 97V42A34 34 0 0 1 84 42V97Z",
    "square": "M24 6H76A18 18 0 0 1 94 24V76A18 18 0 0 1 76 94H24A18 18 0 0 1 6 76V24A18 18 0 0 1 24 6Z",
    "wave_top": "M12 12Q31 2 50 12Q69 2 88 12V52C88 74 70 88 50 96C30 88 12 74 12 52Z",
    "pentagon": "M50 3L96 37L79 95H21L4 37Z",
    "tag": "M50 3C68 3 82 14 82 32V74C82 87 70 97 50 97C30 97 18 87 18 74V32C18 14 32 3 50 3Z",
    "gothic": "M9 8Q50 22 91 8V52C91 74 71 88 50 97C29 88 9 74 9 52Z",
}


def P(d: str, fill: str = "ink", **kw) -> str:
    attrs = "".join(f' {k.replace("_", "-")}="{v}"' for k, v in kw.items())
    return f'<path d="{d}" fill="{fill}"{attrs}/>'


def S(d: str, w: float = 4, color: str = "ink", cap: str = "round") -> str:
    return (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{w}" stroke-linecap="{cap}" '
            f'stroke-linejoin="round"/>')


def C(cx: float, cy: float, r: float, fill: str = "ink") -> str:
    return f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{fill}"/>'


def poly(points) -> str:
    return "M" + "L".join(f"{x:.2f} {y:.2f}" for x, y in points) + "Z"


def waves(y: float, x0: float = 26, x1: float = 74, amp: float = 3.2, n: int = 3) -> str:
    step = (x1 - x0) / (2 * n)
    d = f"M{x0} {y}"
    for i in range(2 * n):
        d += f"Q{x0 + step * (i + 0.5):.2f} {y - amp if i % 2 == 0 else y + amp} {x0 + step * (i + 1):.2f} {y}"
    return d


def star(cx, cy, r_out, r_in, points=5, rot=-90):
    pts = []
    for i in range(points * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(rot + i * 180 / points)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return poly(pts)


# ------------------------------------------------------------------ emblems
def lighthouse() -> str:
    beams = P("M57 30L86 21V39Z", opacity=".55") + P("M43 30L14 21V39Z", opacity=".55")
    tower = P("M43.5 80L46.5 38H53.5L56.5 80Z")
    lantern = P("M44 28.5H56V37H44Z") + P("M43 29L50 20L57 29Z")
    bands = P("M45.4 52H54.6L55 58H45Z", fill="field") + P("M44.6 65H55.4L55.8 71H44.2Z", fill="field")
    window = P("M47.5 30.5H52.5V35H47.5Z", fill="field")
    return beams + tower + lantern + bands + window + S(waves(85, 24, 76, 2.6), 3.2)


def crown() -> str:
    body = P("M29 60L25 34L39 46L50 28L61 46L75 34L71 60Z")
    band = P("M29 62H71V69H29Z")
    jewels = C(25, 31.5, 3.6) + C(50, 25, 3.8) + C(75, 31.5, 3.6) + C(50, 65.5, 2.2, "field")
    return body + band + jewels + S(waves(80, 30, 70, 2.6, 2), 3.2)


def chevrons() -> str:
    def chev(y):
        return P(f"M20 {y + 22}L50 {y}L80 {y + 22}V{y + 33}L50 {y + 11}L20 {y + 33}Z")
    return chev(30) + chev(50) + C(50, 21, 5)


def fern() -> str:
    # A bracken frond: a curved stem with tapering leaflets, rising over the ford.
    out = []
    p0, p1, p2 = (46, 80), (40, 48), (60, 20)
    def bez(t):
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
        dx = 2 * (1 - t) * (p1[0] - p0[0]) + 2 * t * (p2[0] - p1[0])
        dy = 2 * (1 - t) * (p1[1] - p0[1]) + 2 * t * (p2[1] - p1[1])
        return x, y, math.degrees(math.atan2(dy, dx))
    out.append(S(f"M{p0[0]} {p0[1]}Q{p1[0]} {p1[1]} {p2[0]} {p2[1]}", 3.2))
    for i in range(9):
        t = 0.14 + i * 0.095
        x, y, ang = bez(t)
        size = 13.5 * (1 - t) + 3.5
        for side in (-1, 1):
            a = ang + side * 62
            cx = x + math.cos(math.radians(a)) * size * 0.55
            cy = y + math.sin(math.radians(a)) * size * 0.55
            out.append(f'<ellipse cx="{cx:.2f}" cy="{cy:.2f}" rx="{size * 0.6:.2f}" ry="{max(1.6, size * 0.2):.2f}" '
                       f'transform="rotate({a:.1f} {cx:.2f} {cy:.2f})" fill="ink"/>')
    out.append(S(waves(86, 26, 74, 2.4), 3))
    return "".join(out)


def reeds() -> str:
    out = []
    for x, top, h, lean in ((38, 30, 15, -5), (50, 22, 17, 0), (62, 33, 14, 5)):
        out.append(S(f"M{x} 76Q{x + lean * 0.2} {top + 20} {x + lean} {top + h}", 3))
        out.append(f'<rect x="{x + lean - 4:.1f}" y="{top}" width="8" height="{h}" rx="4" fill="ink"/>')
        out.append(S(f"M{x + lean} {top}V{top - 6}", 2.2))
    out.append(S("M50 70Q38 60 30 62", 2.6) + S("M50 72Q63 62 71 64", 2.6))
    return "".join(out) + S(waves(80, 24, 76, 2.4), 3) + S(waves(87, 30, 70, 2.2, 2), 2.6)


def compass() -> str:
    long_pts, short_pts = [], []
    for i in range(8):
        a = math.radians(-90 + i * 45)
        r = 36 if i % 2 == 0 else 19
        long_pts.append((50 + r * math.cos(a), 50 + r * math.sin(a)))
        b = math.radians(-90 + i * 45 + 22.5)
        long_pts.append((50 + 6.5 * math.cos(b), 50 + 6.5 * math.sin(b)))
    ring = '<circle cx="50" cy="50" r="25" fill="none" stroke="ink" stroke-width="2.4"/>'
    return ring + P(poly(long_pts)) + C(50, 50, 4.2, "field") + C(50, 50, 1.8)


def antlers() -> str:
    left = (S("M47 78C41 66 35 56 31 38", 4.6) + S("M34 54L21 47", 4) + S("M32 45L22 34", 4)
            + S("M31 38L29 26", 4) + S("M40 66L30 64", 3.6))
    right = left.replace('d="', 'd="', 1)
    # mirror the left antler across x = 50
    mirrored = f'<g transform="translate(100 0) scale(-1 1)">{left}</g>'
    return left + mirrored + P(star(50, 26, 9, 2.6, 4)) + C(50, 80, 3.4)


def waterwheel() -> str:
    out = ['<circle cx="50" cy="46" r="24" fill="none" stroke="ink" stroke-width="4.6"/>',
           '<circle cx="50" cy="46" r="13" fill="none" stroke="ink" stroke-width="2"/>', C(50, 46, 5)]
    for i in range(8):
        a = math.radians(i * 45 + 22.5)
        x1, y1 = 50 + 5 * math.cos(a), 46 + 5 * math.sin(a)
        x2, y2 = 50 + 24 * math.cos(a), 46 + 24 * math.sin(a)
        out.append(S(f"M{x1:.2f} {y1:.2f}L{x2:.2f} {y2:.2f}", 2.6))
        px, py = 50 + 28.5 * math.cos(a), 46 + 28.5 * math.sin(a)
        out.append(f'<rect x="{px - 4.2:.2f}" y="{py - 2.6:.2f}" width="8.4" height="5.2" rx="1" '
                   f'transform="rotate({i * 45 + 22.5 + 90:.1f} {px:.2f} {py:.2f})" fill="ink"/>')
    return "".join(out) + S(waves(84, 22, 78, 2.6), 3.2)


def rising_sun() -> str:
    out = [P("M31 62A19 19 0 0 1 69 62Z")]
    for i in range(9):
        a = math.radians(180 + 11.25 + i * 19.7)
        r1, r2, w = 23.5, 37 if i % 2 == 0 else 31.5, 4.2
        x1, y1 = 50 + r1 * math.cos(a), 62 + r1 * math.sin(a)
        x2, y2 = 50 + r2 * math.cos(a), 62 + r2 * math.sin(a)
        out.append(S(f"M{x1:.2f} {y1:.2f}L{x2:.2f} {y2:.2f}", w))
    out.append(P("M20 64.5H80V69H20Z"))
    out.append(S(waves(76, 28, 72, 2.4, 3), 3) + S(waves(83, 36, 64, 2.2, 2), 2.6))
    return "".join(out)


def lightning() -> str:
    bolt = P("M55 14L32 52H47L40 82L68 40H52L62 14Z")
    return bolt + S(waves(84, 30, 70, 2.4, 2), 3) + S("M24 30Q30 24 38 26", 2.6) + S("M76 30Q70 24 62 26", 2.6)


def raven() -> str:
    # A perched raven facing left: heavy beak, shaggy throat, long wedge tail.
    body = P("M18 39L30 32L38 27L47 26L54 30L60 38L66 48L76 62L86 80L76 78L68 72L60 72L52 69"
             "L44 62L39 54L36 50L34 47L35 44L28 43Z")
    hackles = P("M36 47L40 50L37 53L41 56L39 58L44 62L40 52Z")
    wing = P("M50 44C58 46 66 54 72 66C64 64 56 60 52 54Z", fill="field", opacity=".5")
    legs = S("M54 70L52 80M60 72L60 80", 2.6) + S("M44 81H72", 3)
    eye = C(42.5, 32.5, 2.2, "field")
    return body + hackles + wing + legs + eye


def hare() -> str:
    body = P(
        "M85 41C83 37 79 34 75 34L70 14C69 11 66 12 66 15L66 32L60 16C59 13 56 14 56 17L60 35"
        "C52 37 44 40 36 45C28 49 22 52 18 55C14 58 14 62 18 62C20 62 22 61 23 60L13 74C12 76 14 78 16 77L32 64"
        "C38 62 46 61 52 60L58 68L70 76C72 77 74 75 72 73L64 64L66 56C72 53 77 49 80 46C83 45 86 44 85 41Z")
    eye = C(77, 39, 1.7, "field")
    return body + eye + S("M22 86H78", 2.4) + S("M30 92H70", 1.8)


def larkspur() -> str:
    out = [S("M50 88V22", 3)]
    blooms = [(50, 22, 4.4), (45, 30, 5.2), (56, 37, 5.8), (44, 45, 6.4), (57, 53, 6.8), (44, 61, 7.0)]
    for cx, cy, r in blooms:
        for k in range(5):
            a = math.radians(-90 + k * 72)
            out.append(C(cx + r * 0.62 * math.cos(a), cy + r * 0.62 * math.sin(a), r * 0.46))
        out.append(C(cx, cy, r * 0.26, "field"))
    out.append(P("M50 84C40 82 32 76 30 68C38 70 46 74 50 80Z") + P("M50 84C60 82 68 76 70 68C62 70 54 74 50 80Z"))
    return "".join(out)


def bridge() -> str:
    deck = P("M14 52H86V78H78V71A8 8 0 0 0 62 71V78H58V71A8 8 0 0 0 42 71V78H38V71A8 8 0 0 0 22 71V78H14Z")
    parapet = P("M14 47H86V50H14Z")
    mural = P("M36 38V22H41V27H47V22H53V27H59V22H64V38Z")
    gate = P("M48 38V33A2 2 0 0 1 52 33V38Z", fill="field")
    return deck + parapet + mural + gate + S(waves(87, 22, 78, 2.2), 2.6)


def acorn() -> str:
    nut = P("M37 52C37 70 43 82 50 84C57 82 63 70 63 52Z")
    cup = P("M33 52C33 42 40 36 50 36C60 36 67 42 67 52Z")
    hatch = S("M38 47L44 41M44 50L54 40M52 50L62 40M60 50L65 45", 1.6, "field")
    stem = S("M50 36C50 30 53 26 57 24", 3.4)
    leaf_l = P("M47 28C38 18 26 18 18 22C22 30 32 36 44 33Z") + S("M45 31C36 25 28 23 21 23", 1.4, "field")
    leaf_r = P("M55 26C62 14 74 12 82 14C80 22 70 30 58 30Z") + S("M57 28C64 21 72 17 80 15", 1.4, "field")
    return leaf_l + leaf_r + nut + cup + hatch + stem


def crescent() -> str:
    # Crescent: the outer circle minus an offset circle (even-odd), over the lea.
    moon = ('<path fill-rule="evenodd" fill="ink" d="M52 18A24 24 0 1 0 52 66A24 24 0 1 0 52 18Z'
            'M61 16A21 21 0 1 0 61 58A21 21 0 1 0 61 16Z"/>')
    lea = S("M22 80Q36 74 50 80T78 80", 3) + S("M28 88Q39 83 50 88T72 88", 2.6)
    return moon + P(star(70, 40, 5, 1.8, 4)) + lea


def westmarch() -> str:
    peaks = P("M12 82L36 46L48 62L62 40L88 82Z")
    snow = P("M36 46L42 55L36 52L31 54Z", fill="field") + P("M62 40L69 51L62 48L56 50Z", fill="field")
    pole = P("M61 40V16H63.6V40Z")
    flag = P("M63.6 17C70 15 74 20 82 17V31C74 34 70 29 63.6 31Z")
    return peaks + snow + pole + flag + S("M18 88H82", 2.4)


def flame() -> str:
    outer = P("M50 12C53 26 70 36 70 58C70 72 61 84 50 84C39 84 30 72 30 58C30 46 37 40 40 32"
              "C42 40 45 44 48 46C46 34 47 22 50 12Z")
    inner = P("M50 50C54 58 60 62 60 70C60 76 55 80 50 80C45 80 40 76 40 70C40 63 46 60 50 50Z", fill="field")
    embers = C(28, 30, 2.4) + C(73, 26, 2) + C(76, 44, 1.6)
    return outer + inner + embers


def peaks() -> str:
    back = P("M30 78L54 32L78 78Z", opacity=".55")
    front = P("M12 82L34 46L46 64L58 48L88 82Z")
    snow = P("M34 46L40 56L34 53L29 55Z", fill="field") + P("M58 48L65 58L58 55L53 57Z", fill="field")
    sun = C(28, 26, 6.5)
    return back + front + snow + sun + S("M18 88H82", 2.4)


def anchor() -> str:
    ring = '<circle cx="50" cy="20" r="6" fill="none" stroke="ink" stroke-width="3.6"/>'
    shank = P("M47.5 26H52.5V78H47.5Z")
    stock = P("M34 34H66V40H34Z") + C(34, 37, 3.2) + C(66, 37, 3.2)
    arms = S("M24 58C26 72 38 80 50 80C62 80 74 72 76 58", 5)
    flukes = P("M18 62L24 52L30 62Z") + P("M70 62L76 52L82 62Z")
    return ring + shank + stock + arms + flukes


# ------------------------------------------------------------------ the league
CLUBS = {
    #       name                   shape        emblem       field      ink        rim
    "C01": ("Harbourside Rovers", "roundel", lighthouse, "#D3D7DE", "#1A3A5C", "#1A3A5C"),
    "C02": ("Kingsmere Athletic", "heater", crown, "#7A1F2B", "#E6DEEA", "#E6DEEA"),
    "C03": ("Wexley United", "round_base", chevrons, "#C8102E", "#F2F2F2", "#F2F2F2"),
    "C04": ("Brackenford City", "kite", fern, "#5BA3D9", "#FFFFFF", "#0F3557"),
    "C05": ("Saltmarsh Town", "octagon", reeds, "#E0A526", "#1C1C1C", "#1C1C1C"),
    "C06": ("Hollowell Wanderers", "oval", compass, "#2E6B3A", "#F4E9C8", "#F4E9C8"),
    "C07": ("Northwick Forest", "heater", antlers, "#1F5130", "#D8B26E", "#D8B26E"),
    "C08": ("Calder Mills", "hex_point", waterwheel, "#6B4F78", "#F4F1F6", "#F4F1F6"),
    "C09": ("Eastholme Rangers", "ogee", rising_sun, "#0E4C92", "#F5C400", "#F5C400"),
    "C10": ("Stormhaven", "diamond", lightning, "#3B4A57", "#9FD3E6", "#9FD3E6"),
    "C11": ("Ravensgate Albion", "castle", raven, "#111111", "#D3D7DE", "#D3D7DE"),
    "C12": ("Millbrook Harriers", "banner", hare, "#E35205", "#101820", "#101820"),
    "C13": ("Larkspur Park", "arch", larkspur, "#8F7BC6", "#FFFFFF", "#FFFFFF"),
    "C14": ("Fenwick Borough", "square", bridge, "#A3262A", "#F4EEE6", "#F4EEE6"),
    "C15": ("Oakhurst United", "wave_top", acorn, "#4E7D2F", "#FFFFFF", "#FFFFFF"),
    "C16": ("Silverlea", "hex_flat", crescent, "#A7AEB6", "#232A33", "#232A33"),
    "C17": ("Westmarch", "pentagon", westmarch, "#7C2D12", "#FDE68A", "#FDE68A"),
    "C18": ("Cindervale", "tag", flame, "#3F3F46", "#F97316", "#F97316"),
    "C19": ("Highmoor Athletic", "gothic", peaks, "#155E75", "#ECFEFF", "#ECFEFF"),
    "C20": ("Port Elsworth", "roundel", anchor, "#1E3A8A", "#FCA5A5", "#FCA5A5"),
}


def crest_svg(club_id: str) -> str:
    name, shape, emblem, field, ink, rim = CLUBS[club_id]
    d = SHAPES[shape]
    art = emblem().replace('"ink"', f'"{ink}"').replace('"field"', f'"{field}"')
    rope = ""
    if club_id == "C20":  # a rope ring for the port
        rope = (f'<circle cx="50" cy="50" r="40" fill="none" stroke="{ink}" stroke-width="2.6" '
                f'stroke-dasharray="3.2 2.2" opacity=".85"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" role="img" aria-label="{name} crest">'
        f'<title>{name}</title>'
        f'<path d="{d}" fill="{field}" stroke="{rim}" stroke-width="3" stroke-linejoin="round"/>'
        f'<path d="{d}" fill="none" stroke="{ink}" stroke-opacity=".45" stroke-width="1.4" '
        f'vector-effect="non-scaling-stroke" transform="translate(50 50) scale(.84) translate(-50 -50)"/>'
        f'{rope}<g transform="translate(50 50) scale(.86) translate(-50 -50)">{art}</g></svg>'
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for cid in CLUBS:
        (OUT / f"{cid}.svg").write_text(crest_svg(cid) + "\n")
    print(f"wrote {len(CLUBS)} crests to {OUT}")


if __name__ == "__main__":
    main()
