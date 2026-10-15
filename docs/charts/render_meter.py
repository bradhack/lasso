"""Render the showcase Gaffer's Gauge chart (docs/img/gaffers_gauge_example.png).

    python docs/charts/render_meter.py

A 100% stacked area (home win / draw / away win) over the match, drawn as SVG in
the app's design language and rasterized with Playwright. Data comes from
data/model/demo_trajectory.json (written by `python -m lasso_engine.evaluate`).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MATCH = "S5-MD07-03"
FONTS = ROOT / "web" / "node_modules" / "@fontsource"

BG, CARD, LINE, INK, MUTED, SOFT = "#0A1020", "#111A2E", "#34466B", "#F2F5FA", "#8E9AB3", "#B8C3D6"
HOME, DRAW, AWAY, RED = "#E6EBF2", "#34466B", "#7B93C4", "#FF6B7A"
GOLD = "#C9A45C"


def load() -> tuple[list[dict], dict, dict]:
    traj = json.loads((ROOT / "data/model/demo_trajectory.json").read_text())
    m = pd.read_parquet(ROOT / "data/demo/matches.parquet").set_index("match_id").loc[MATCH]
    clubs = pd.read_parquet(ROOT / "data/demo/clubs.parquet").set_index("club_id")
    meta = {"home": clubs.loc[m.home_id, "name"], "away": clubs.loc[m.away_id, "name"],
            "home_short": clubs.loc[m.home_id, "short"], "away_short": clubs.loc[m.away_id, "short"],
            "score": (int(m.home_goals), int(m.away_goals)), "added_1h": float(m.added_1h)}
    events = [{"elapsed": r["elapsed"], "note": r["note"]} for r in traj if r["note"]]
    return traj, meta, events


def meter_svg(traj: list[dict], meta: dict, events: list[dict], w: float, h: float,
              labels: bool = True) -> str:
    """The chart itself: plot area w x h, with event markers and in-band labels."""
    xmax = traj[-1]["elapsed"]
    X = lambda e: e / xmax * w  # noqa: E731
    Y = lambda p: h - p * h  # noqa: E731
    pts = sorted(traj, key=lambda r: r["elapsed"])
    top_home = [(X(r["elapsed"]), Y(r["home"])) for r in pts]
    top_draw = [(X(r["elapsed"]), Y(r["home"] + r["draw"])) for r in pts]

    def poly(upper, lower) -> str:
        pts_ = upper + list(reversed(lower))
        return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts_) + " Z"

    base = [(x, h) for x, _ in top_home]
    ceiling = [(x, 0.0) for x, _ in top_home]
    out = [
        f'<path d="{poly(top_home, base)}" fill="{HOME}"/>',
        f'<path d="{poly(top_draw, top_home)}" fill="{DRAW}"/>',
        f'<path d="{poly(ceiling, top_draw)}" fill="{AWAY}"/>',
        # 2px surface gaps between bands keep the boundaries crisp.
        f'<path d="M{" L".join(f"{x:.1f},{y:.1f}" for x, y in top_home)}" fill="none" stroke="{BG}" '
        f'stroke-width="2.5" stroke-linejoin="round"/>',
        f'<path d="M{" L".join(f"{x:.1f},{y:.1f}" for x, y in top_draw)}" fill="none" stroke="{BG}" '
        f'stroke-width="2.5" stroke-linejoin="round"/>',
    ]
    for ev in events:
        x = X(ev["elapsed"])
        out.append(f'<line x1="{x:.1f}" y1="-26" x2="{x:.1f}" y2="{h}" stroke="{BG}" stroke-width="2" '
                   f'stroke-opacity="0.55"/>')
    if labels:
        # Direct labels inside each band at the 30th minute.
        at = min(pts, key=lambda r: abs(r["elapsed"] - 30))
        x = X(at["elapsed"]) + 14
        mid = lambda a, b: (Y(a) + Y(b)) / 2  # noqa: E731
        rows = [
            (mid(0, at["home"]), f"{meta['home'].upper()} WIN", at["home"], BG),
            (mid(at["home"], at["home"] + at["draw"]), "DRAW", at["draw"], INK),
            (mid(at["home"] + at["draw"], 1), f"{meta['away'].upper()} WIN", at["away"], BG),
        ]
        for y, txt, p, color in rows:
            out.append(f'<text x="{x:.1f}" y="{y + 7:.1f}" fill="{color}" font-family="DM Sans" '
                       f'font-weight="700" font-size="17" letter-spacing="1.2">{txt} '
                       f'<tspan font-family="Barlow Condensed" font-weight="600" font-size="22">'
                       f'{round(p * 100)}%</tspan></text>')
    return "\n".join(out)


def page(traj: list[dict], meta: dict, events: list[dict]) -> str:
    W, H = 1600, 900
    left, top, pw, ph = 96, 350, 1330, 430
    xmax = traj[-1]["elapsed"]
    X = lambda e: left + e / xmax * pw  # noqa: E731
    a1 = meta["added_1h"]
    ticks = [(0, "0'"), (15, "15'"), (30, "30'"), (45 + a1, "HT"), (60 + a1, "60'"), (75 + a1, "75'"),
             (90 + a1, "90'")]
    pins = []
    for ev in events:
        kind = "red" if ev["note"].startswith("Red") else "goal"
        team, minute = ev["note"].split("(")[1].split(")")[0], ev["note"].split()[-1]
        pins.append({"x": X(ev["elapsed"]), "kind": kind, "team": team, "minute": minute})
    # Stagger pin labels that would collide.
    rows, last_x = [], -999.0
    for p in pins:
        p["row"] = 1 if p["x"] - last_x < 150 and (not rows or rows[-1] == 0) else 0
        rows.append(p["row"])
        last_x = p["x"]

    winner = next(r for r in traj if r["elapsed"] >= events[-1]["elapsed"])
    before = max((r for r in traj if r["elapsed"] < events[-1]["elapsed"]), key=lambda r: r["elapsed"])
    fx = X(events[-1]["elapsed"])

    def font(fam: str, w: int) -> str:
        slug = fam.lower().replace(" ", "-")
        f = FONTS / slug / "files" / f"{slug}-latin-{w}-normal.woff2"
        return f"@font-face{{font-family:'{fam}';font-weight:{w};src:url('file://{f}') format('woff2');}}"

    fonts = "".join(font(f, w) for f, w in [("Barlow Condensed", 600), ("Barlow Condensed", 700),
                                            ("DM Sans", 400), ("DM Sans", 500), ("DM Sans", 700),
                                            ("Sora", 700)])
    pin_svg = []
    for p in pins:
        y = top - 34 - p["row"] * 44
        color = RED if p["kind"] == "red" else (HOME if p["team"] == meta["home_short"] else AWAY)
        label = ("RED CARD " if p["kind"] == "red" else "GOAL ") + f"{p['team']} {p['minute']}"
        tw = 9.2 * len(label) + 34
        pin_svg.append(
            f'<line x1="{p["x"]:.1f}" y1="{y + 16}" x2="{p["x"]:.1f}" y2="{top}" stroke="{LINE}" stroke-width="2"/>'
            f'<rect x="{p["x"] - 12:.1f}" y="{y - 16}" rx="16" width="{tw:.0f}" height="32" fill="{CARD}" '
            f'stroke="{LINE}"/>'
            + (f'<rect x="{p["x"] - 4:.1f}" y="{y - 7}" width="9" height="13" rx="2" fill="{RED}"/>'
               if p["kind"] == "red" else
               f'<circle cx="{p["x"]:.1f}" cy="{y}" r="6" fill="{color}"/>')
            + f'<text x="{p["x"] + 14:.1f}" y="{y + 6}" fill="{INK}" font-family="DM Sans" font-weight="700" '
              f'font-size="15" letter-spacing="0.6">{label}</text>')
    tick_svg = "".join(
        f'<text x="{X(e):.1f}" y="{top + ph + 34}" fill="{MUTED}" font-family="DM Sans" font-size="16" '
        f'text-anchor="middle">{t}</text>' for e, t in ticks)
    ht_x = X(45 + a1)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{fonts}
html,body{{margin:0;background:{BG};}}</style></head><body>
<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
<rect width="{W}" height="{H}" fill="{BG}"/>
<g transform="translate(96,0)">
  <g transform="translate(0,78)" fill="{GOLD}"><g transform="scale(1.6)" fill="none" stroke="{GOLD}"
    stroke-width="1.8" stroke-linecap="round"><ellipse cx="13.5" cy="9" rx="7.5" ry="5"/>
    <path d="M8.5 12.5c-1.5 2-1.2 4 .6 5s2.2 2.6.6 4.5"/></g></g>
  <text x="48" y="104" fill="{INK}" font-family="Sora" font-weight="700" font-size="28">lasso</text>
  <text x="150" y="104" fill="{GOLD}" font-family="DM Sans" font-weight="700" font-size="16"
    letter-spacing="2.4">GAFFER’S GAUGE · HELD-OUT SEASON REPLAY</text>
  <text x="0" y="172" fill="{INK}" font-family="Barlow Condensed" font-weight="600" font-size="58"
    letter-spacing="0.5">{meta['home'].upper()} {meta['score'][0]} : {meta['score'][1]} {meta['away'].upper()}</text>
  <text x="0" y="214" fill="{SOFT}" font-family="DM Sans" font-size="21">Down to ten men in the 5th minute.
    The Gaffer gave {meta['home']} {round(before['home'] * 100)}% when they scored the winner.</text>
</g>
<rect x="{ht_x - 1:.1f}" y="{top}" width="2" height="{ph}" fill="{BG}" fill-opacity="0.7"/>
<g transform="translate({left},{top})">{meter_svg(traj, meta, events, pw, ph)}</g>
<line x1="{left}" y1="{top + ph / 2}" x2="{left + pw}" y2="{top + ph / 2}" stroke="{BG}" stroke-opacity="0.35"
  stroke-dasharray="2 6"/>
{"".join(pin_svg)}
{tick_svg}
<text x="{left + pw + 18}" y="{top + 6}" fill="{MUTED}" font-family="DM Sans" font-size="15">100%</text>
<text x="{left + pw + 18}" y="{top + ph / 2 + 5}" fill="{MUTED}" font-family="DM Sans" font-size="15">50%</text>
<text x="{left + pw + 18}" y="{top + ph + 5}" fill="{MUTED}" font-family="DM Sans" font-size="15">0%</text>
<g transform="translate({fx - 300:.1f},{top + 120})">
  <rect width="270" height="118" rx="20" fill="{CARD}" stroke="{GOLD}" stroke-width="1.5"/>
  <text x="22" y="34" fill="{GOLD}" font-family="DM Sans" font-weight="700" font-size="14"
    letter-spacing="1.6">82' WINNER</text>
  <text x="22" y="88" fill="{INK}" font-family="Barlow Condensed" font-weight="600" font-size="54">
    {round(before['home'] * 100)}%<tspan fill="{MUTED}" font-size="40"> → </tspan>{round(winner['home'] * 100)}%</text>
  <text x="22" y="108" fill="{MUTED}" font-family="DM Sans" font-size="13">{meta['home']} win chance</text>
</g>
<text x="96" y="{H - 34}" fill="{MUTED}" font-family="DM Sans" font-size="15">The Gaffer: hierarchical Bayesian
  team strengths with Gamma-Poisson live updating. Each band is a live probability; they always sum to 100%.
  Synthetic league, fictional clubs.</text>
</svg></body></html>"""


async def render(out: Path) -> None:
    from playwright.async_api import async_playwright

    traj, meta, events = load()
    html = ROOT / "docs" / "charts" / "gaffers_gauge.html"
    html.write_text(page(traj, meta, events))
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1600, "height": 900}, device_scale_factor=2)
        await pg.goto(html.as_uri())
        await pg.wait_for_timeout(600)
        await pg.screenshot(path=str(out))
        await b.close()


if __name__ == "__main__":
    asyncio.run(render(ROOT / "docs" / "img" / "gaffers_gauge_example.png"))
    print("wrote docs/img/gaffers_gauge_example.png")
