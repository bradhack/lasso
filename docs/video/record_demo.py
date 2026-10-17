"""Record Lasso's demo video from the live app, in sync with its narration script.

    python docs/video/record_demo.py https://<your app> --key <admin key>

It replays the showcase match from the 77th minute (slowed down so each scene has time for its lines), signs in a
demo fan of Eastholme Rangers, and drives a 1920x1080 browser through the scenes below: the Gauge, Why it moved,
Ask the Gaffer, Call it, Penke's winner, Under the hood, then four slides (Microsoft Fabric, two agents or one, how
it works, the close). It captures the screen as it goes and writes, in docs/video/out/:

    lasso-demo.mp4   the video, 1080p, no sound: record your narration over it
    lasso-demo.srt   the narration as captions, timed to the video (read along, or upload to YouTube as captions)
    narration.md     each scene's start time and lines, to read from while you record

Every scene lasts at least as long as its lines take to say (about 2.4 words a second), and longer when the live
match makes it wait (an answer arriving, the goal, the agents' story). The script itself lives in SCENES below;
`--script-only` writes docs/video/SCRIPT.md from it without recording.

Needs: Python 3.10+, `pip install playwright` then `playwright install chromium`, and ffmpeg on the PATH
(Windows: `winget install Gyan.FFmpeg`). It restarts the showcase match for anyone watching, and creates one demo
fan (named "Brad" unless you pass --name).
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

MATCH = "S5-MD07-03"  # the showcase: Eastholme Rangers 2-1 Brackenford City, Penke's winner at 82'
HERE = Path(__file__).resolve().parent
IMG = HERE.parent / "img"
WORDS_PER_SECOND = 2.4

# The script: one entry per scene, in order. "line" is what you say; the scene lasts at least as long as it takes.
SCENES = [
    {"id": "gauge", "title": "The Gaffer's Gauge",
     "show": "The live match at 77': Eastholme Rangers 1-1 Brackenford City, Eastholme down to ten. The Gauge glows.",
     "line": "This is Lasso: watch a live match with the Gaffer, our AI, at your side. Eastholme are down to ten, "
             "and the Gaffer's Gauge makes them long shots."},
    {"id": "why", "title": "Why it moved",
     "show": "Why it moved glows: the agents' latest story, in plain words.",
     "line": "The numbers come from a Bayesian model, and seven AI agents explain them. Why it moved says what "
             "changed the chances, in plain words and four languages."},
    {"id": "ask", "title": "Ask the Gaffer",
     "show": "Typing \"Can Eastholme still win this?\" into Ask the Gaffer; the answer arrives with its AI agents chip.",
     "line": "Ask the Gaffer anything. A Scout agent picks the data tools over MCP; then the Gaffer, with no tools "
             "of its own, writes the answer."},
    {"id": "callit", "title": "Call it",
     "show": "Call it: \"Eastholme Rangers score before 89'?\" Yes, then Lasso it.",
     "line": "Then call it, priced at the Gaffer's own odds. Eastholme to score is a long shot, so it pays big. "
             "No money, just biscuits."},
    {"id": "goal", "title": "Penke's winner",
     "show": "82': Penke scores, the Gauge jumps, Called it! pays out, and the agents' story replaces the instant one.",
     "line": "Penke scores! The Gauge leaps past 80 percent, the call pays out, and the agents' story follows seconds "
             "later."},
    {"id": "hood", "title": "Under the hood",
     "show": "Under the hood for the goal's story: five agents in two rounds, their tools, and Checked by code.",
     "line": "Under the hood shows the teamwork: five agents in two rounds, the tools they called, and what our "
             "code checks caught."},
    {"id": "fabric", "title": "Microsoft Fabric",
     "show": "Slide: the Lasso agents dashboard in Microsoft Fabric, panning down.",
     "line": "Every story, answer and agent run streams to Microsoft Fabric: speed, cost, the slips caught, and "
             "how the agents recover."},
    {"id": "compare", "title": "Two agents or one",
     "show": "Slide: the Press Room against one agent alone, on the same 27 questions.",
     "line": "Is the team worth it? On the same 27 questions, two agents passed all 27; one agent alone passed 25."},
    {"id": "arch", "title": "How it's built",
     "show": "Slide: how Lasso works, seven agents and one live pipeline.",
     "line": "Built on Microsoft Agent Framework and Foundry, with A2A, MCP, Event Hubs, Web PubSub, Cosmos DB "
             "and Container Apps."},
    {"id": "close", "title": "Close",
     "show": "Slide: the Lasso cover.",
     "line": "Lasso. Believe your call."},
]
for s in SCENES:
    s["min"] = round(len(s["line"].split()) / WORDS_PER_SECOND + 1.2, 1)


# ---------------------------------------------------------------- the script, as a document

def write_script(path: Path) -> None:
    total = sum(s["min"] for s in SCENES)
    out = ["# Lasso demo video: the script", "",
           f"About {total:.0f} seconds of narration (the recording runs a little longer while the live match plays). "
           "Generated from `docs/video/record_demo.py`, which records the video to match: run it, then read these "
           "lines over the video, using `out/narration.md` for each scene's exact start time.", "",
           "| # | Scene | On screen | Say | At least |", "|---|---|---|---|---|"]
    for i, s in enumerate(SCENES, 1):
        out.append(f"| {i} | {s['title']} | {s['show']} | {s['line']} | {s['min']:.0f}s |")
    out += ["", f"{sum(len(s['line'].split()) for s in SCENES)} words in all."]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- the app's API

def http(app: str, method: str, path: str, body: dict | None = None, key: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-Admin-Key"] = key
    req = urllib.request.Request(app + path, method=method, headers=headers,
                                 data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
    return json.loads(raw) if raw else {}


# ---------------------------------------------------------------- what the viewer sees besides the app

OVERLAY_CSS = """
#demo-cursor { position: fixed; z-index: 99999; width: 22px; height: 22px; margin: -11px 0 0 -11px; border-radius: 50%;
  background: rgba(255,255,255,.92); box-shadow: 0 0 0 4px rgba(201,164,92,.55), 0 4px 14px rgba(0,0,0,.5);
  left: 960px; top: 560px; transition: left .7s cubic-bezier(.2,.8,.2,1), top .7s cubic-bezier(.2,.8,.2,1), transform .15s;
  pointer-events: none; }
#demo-cursor.press { transform: scale(.7); }
.demo-glow { box-shadow: 0 0 0 3px #C9A45C, 0 0 36px rgba(201,164,92,.45) !important; transition: box-shadow .5s; }
#demo-slide { position: fixed; inset: 0; z-index: 100000; background: #0A1020; color: #F2F5FA; overflow: hidden;
  font-family: 'DM Sans', system-ui, sans-serif; opacity: 0; transition: opacity .6s; }
#demo-slide.on { opacity: 1; }
#demo-slide h1 { font-family: 'Barlow Condensed', 'Arial Narrow', sans-serif; font-weight: 600; font-size: 68px;
  margin: 0; letter-spacing: .01em; }
#demo-slide .eyebrow { font-family: 'Barlow Condensed', 'Arial Narrow', sans-serif; font-weight: 600; font-size: 28px;
  letter-spacing: .12em; color: #C9A45C; }
@keyframes demo-pan { from { transform: translateY(0); } to { transform: translateY(var(--pan)); } }
@keyframes demo-zoom { from { transform: scale(1); } to { transform: scale(1.06); } }
"""

def data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def slide_html(scene: str, seconds: float) -> str:
    d = f"{max(4.0, seconds):.1f}s"
    if scene == "fabric":
        return (f"<div style='position:absolute;left:120px;top:70px'><div class='eyebrow'>MICROSOFT FABRIC</div>"
                f"<h1>The agents, live</h1></div>"
                f"<div style='position:absolute;left:120px;right:120px;top:230px;bottom:0;overflow:hidden;"
                f"border-radius:22px 22px 0 0'><img src='{data_uri(IMG / 'fabric-dashboard.png')}' style='width:100%;"
                f"display:block;--pan:-48%;animation:demo-pan {d} ease-in-out forwards'></div>")
    if scene == "compare":
        def col(name: str, passed: str, secs: str, note: str, gold: bool) -> str:
            border = "#C9A45C" if gold else "#22304D"
            return (f"<div style='flex:1;padding:44px 48px;border-radius:28px;background:#111A2E;border:2px solid "
                    f"{border}'><div style='font-size:30px;font-weight:700'>{name}</div>"
                    f"<div style='font-family:Barlow Condensed,Arial Narrow,sans-serif;font-weight:600;font-size:150px;"
                    f"line-height:1;margin-top:18px;color:{'#C9A45C' if gold else '#E6EBF2'}'>{passed}</div>"
                    f"<div style='font-size:26px;color:#B8C3D6;margin-top:6px'>passed every check</div>"
                    f"<div style='font-size:26px;color:#DCE3EE;margin-top:26px'>{secs} typical answer</div>"
                    f"<div style='font-size:24px;color:#8E9AB3;margin-top:22px;line-height:1.45'>{note}</div></div>")
        return ("<div style='position:absolute;inset:150px 140px'><div class='eyebrow'>TWO AGENTS OR ONE?</div>"
                "<h1>Same 27 questions, same checks, the live app</h1>"
                "<div style='display:flex;gap:44px;margin-top:56px'>"
                + col("Press Room: Scout, then the Gaffer", "27/27", "8.0s",
                      "The writer has no tools, so a fan's words can't make it do anything.", True)
                + col("One agent alone", "25/27", "5.2s",
                      "Answered a Spanish fan half in English: &ldquo;están level 1-1 and still have a 24% opci&oacute;n "
                      "to win&rdquo;. Once ran out of time.", False)
                + "</div><div style='margin-top:40px;font-size:22px;color:#8E9AB3'>One evaluation run each, on the "
                "live app, October 17, 2026. Every answer, side by side: docs/agent-comparison.md</div></div>")
    if scene == "arch":
        return (f"<img src='{data_uri(IMG / 'submission-2-how-it-works.png')}' style='position:absolute;inset:0;"
                f"width:100%;height:100%;object-fit:cover;animation:demo-zoom {d} ease-out forwards'>")
    return (f"<img src='{data_uri(IMG / 'submission-1-cover.png')}' style='position:absolute;inset:0;width:100%;"
            f"height:100%;object-fit:cover;animation:demo-zoom {d} ease-out forwards'>")


# ---------------------------------------------------------------- the recorder

class Recorder:
    def __init__(self, page, cdp, frames_dir: Path):
        self.page, self.cdp, self.dir = page, cdp, frames_dir
        self.frames: list[tuple[float, Path]] = []
        self.t0 = time.monotonic()
        self.starts: list[tuple[dict, float]] = []

    def now(self) -> float:
        return time.monotonic() - self.t0

    def start(self) -> None:
        def on_frame(ev):
            path = self.dir / f"{len(self.frames):06d}.jpg"
            path.write_bytes(base64.b64decode(ev["data"]))
            self.frames.append((self.now(), path))
            try:
                self.cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})
            except Exception:  # noqa: BLE001
                pass
        self.cdp.on("Page.screencastFrame", on_frame)
        self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": 1920,
                                               "maxHeight": 1080, "everyNthFrame": 1})
        self.t0 = time.monotonic()

    def stop(self) -> None:
        self.cdp.send("Page.stopScreencast")

    def wait(self, seconds: float) -> None:
        """Wait while still capturing: the page keeps producing frames as it animates."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.page.wait_for_timeout(min(250, max(1, int((end - time.monotonic()) * 1000))))

    def scene(self, scene_id: str) -> dict:
        s = next(x for x in SCENES if x["id"] == scene_id)
        self.starts.append((s, self.now()))
        print(f"  {self.now():6.1f}s  {s['title']}")
        return s

    def hold(self, s: dict) -> None:
        """Keep the scene on screen until its lines have had time to be said."""
        start = next(t for x, t in self.starts if x is s)
        left = start + s["min"] - self.now()
        if left > 0:
            self.wait(left)


def cursor_to(rec: Recorder, locator, click: bool = True) -> None:
    locator.scroll_into_view_if_needed(timeout=10000)
    box = locator.bounding_box()
    if not box:
        return
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    rec.page.evaluate("([x, y]) => { const c = document.getElementById('demo-cursor'); c.style.left = x + 'px';"
                      " c.style.top = y + 'px'; }", [x, y])
    rec.wait(0.8)
    if click:
        rec.page.evaluate("() => { const c = document.getElementById('demo-cursor'); c.classList.add('press');"
                          " setTimeout(() => c.classList.remove('press'), 180); }")
        locator.click()
        rec.wait(0.3)


def glow(rec: Recorder, selector: str | None) -> None:
    rec.page.evaluate("(sel) => { document.querySelectorAll('.demo-glow').forEach(e => e.classList.remove('demo-glow'));"
                      " if (sel) { const e = document.querySelector(sel); if (e) e.classList.add('demo-glow'); } }",
                      selector)


def show_slide(rec: Recorder, scene: dict) -> None:
    html = slide_html(scene["id"], scene["min"])
    rec.page.evaluate("(html) => { let s = document.getElementById('demo-slide'); if (!s) { s = document.createElement('div');"
                      " s.id = 'demo-slide'; document.body.appendChild(s); } s.classList.remove('on'); s.innerHTML = html;"
                      " requestAnimationFrame(() => requestAnimationFrame(() => s.classList.add('on'))); }", html)


def run(app: str, key: str, out: Path, pace: float, from_minute: int, name: str = "Brad") -> None:
    from playwright.sync_api import sync_playwright

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg isn't on the PATH. On Windows: winget install Gyan.FFmpeg (then open a new terminal).")
    out.mkdir(parents=True, exist_ok=True)
    frames_dir = out / "frames"
    shutil.rmtree(frames_dir, ignore_errors=True)
    frames_dir.mkdir()

    match = http(app, "GET", f"/api/matches/{MATCH}")
    home = match["home"]
    user = http(app, "POST", "/api/users", {"name": name[:24], "club_id": home["club_id"]})
    http(app, "PATCH", f"/api/users/{user['id']}", {"lang": "en", "persona": "fan"})
    print(f"Demo fan {user['id']} supports {home['name']}. Restarting the showcase match from {from_minute}' "
          f"at {pace:g} seconds a minute...")
    http(app, "POST", f"/api/admin/matches/{MATCH}/restart?from_minute={from_minute}&minute_seconds={pace}", {}, key)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        ctx.add_init_script(f"try {{ localStorage.setItem('lasso.user', {json.dumps(user['id'])}); }} catch (e) {{}}")
        page = ctx.new_page()
        page.goto(f"{app}/#/match/{MATCH}")
        page.add_style_tag(content=OVERLAY_CSS)
        page.evaluate("() => { const c = document.createElement('div'); c.id = 'demo-cursor';"
                      " document.body.appendChild(c); }")
        page.wait_for_selector(".card.why", timeout=60000)

        def minute() -> int:
            try:
                return int(http(app, "GET", f"/api/matches/{MATCH}").get("minute") or 0)
            except Exception:  # noqa: BLE001
                return 0

        while minute() < from_minute:  # the restart may pause briefly before kickoff of the replay
            page.wait_for_timeout(1000)
        page.wait_for_timeout(1500)

        rec = Recorder(page, ctx.new_cdp_session(page), frames_dir)
        rec.start()
        print("Recording:")

        s = rec.scene("gauge")
        glow(rec, ".app.wide section.card")  # the score and the Gauge
        rec.hold(s)

        s = rec.scene("why")
        glow(rec, ".card.why")
        rec.hold(s)

        s = rec.scene("ask")
        glow(rec, ".card.ask")
        box = page.locator("#ask-question")
        cursor_to(rec, box)
        box.type("Can Eastholme still win this?", delay=70)
        rec.wait(0.4)
        cursor_to(rec, page.locator(".card.ask button.cta"))
        try:
            page.wait_for_selector(".card.ask .bubble.gaffer:not(.thinking)", timeout=40000)
        except Exception:  # noqa: BLE001
            print("    (the answer took over 40 seconds; carrying on)")
        rec.hold(s)
        rec.wait(1.5)  # time to read the answer

        s = rec.scene("callit")
        glow(rec, "section.callit")
        try:  # the market that matters: Eastholme to score before the 89th minute
            page.wait_for_function("() => /score before 8[5-9]/.test(document.querySelector('section.callit')?.innerText"
                                   " || '') && /Eastholme/.test(document.querySelector('section.callit')?.innerText || '')",
                                   timeout=45000)
        except Exception:  # noqa: BLE001
            print("    (no Eastholme-to-score call yet; using the one open now)")
        callit = page.locator("section.callit")
        callit.scroll_into_view_if_needed()
        rec.wait(0.8)
        yes = callit.locator("button.opt").first
        if yes.count():
            cursor_to(rec, yes)
            lasso = callit.locator("button.cta")
            if lasso.count() and lasso.is_enabled():
                cursor_to(rec, lasso)
        rec.hold(s)

        s = rec.scene("goal")
        page.evaluate("() => window.scrollTo({ top: 0, behavior: 'smooth' })")
        glow(rec, ".app.wide section.card")
        try:
            page.wait_for_function(f"() => fetch('/api/matches/{MATCH}').then(r => r.json())"
                                   ".then(m => (m.score || [0, 0])[0] >= 2)", timeout=120000, polling=1000)
        except Exception:  # noqa: BLE001
            print("    (no goal within two minutes: check the replay pace)")
        rec.wait(2.5)
        glow(rec, ".card.why")
        try:  # the agents' story for the goal: Why it moved gets its "AI agents" chip
            page.wait_for_function("() => { const w = document.querySelector('.card.why');"
                                   " return w && /82'/.test(w.innerText) && w.querySelector('.chip.agents'); }",
                                   timeout=30000, polling=500)
        except Exception:  # noqa: BLE001
            print("    (the agents' story for the goal hadn't arrived after 30 seconds)")
        rec.hold(s)
        rec.wait(1.0)

        s = rec.scene("hood")
        glow(rec, None)
        chip = page.locator(".card.why .chip.agents")
        if chip.count():
            cursor_to(rec, chip)
            page.wait_for_selector(".sheet .uth", timeout=10000)
            rec.wait(2.0)
            sheet = page.locator(".sheet-inner.uth")
            steps = 6
            for i in range(1, steps + 1):  # scroll down to Checked by code
                sheet.evaluate(f"(el) => el.scrollTo({{ top: el.scrollHeight * {i / steps}, behavior: 'smooth' }})")
                rec.wait(max(0.6, (s["min"] - 3.5) / steps))
        rec.hold(s)
        if page.locator(".sheet").count():
            cursor_to(rec, page.locator(".sheet .uth button.cta"))

        for scene_id in ("fabric", "compare", "arch", "close"):
            s = rec.scene(scene_id)
            show_slide(rec, s)
            rec.hold(s)
        rec.wait(1.0)
        end = rec.now()
        rec.stop()
        browser.close()

    encode(rec, end, out)
    write_captions(rec, end, out)
    print(f"\nDone: {out / 'lasso-demo.mp4'} ({end:.0f} seconds), with lasso-demo.srt and narration.md.")
    if end > 119:
        print("It's over two minutes: the live match made some scenes wait. Run it again, or trim the goal scene's "
              "wait in a video editor.")


def encode(rec: Recorder, end: float, out: Path) -> None:
    """Frames arrive only when the screen changes: give each one the time until the next, then encode at 30 fps."""
    lst = out / "frames.txt"
    lines = ["ffconcat version 1.0"]
    for i, (t, path) in enumerate(rec.frames):
        nxt = rec.frames[i + 1][0] if i + 1 < len(rec.frames) else end
        lines += [f"file '{path.resolve().as_posix()}'", f"duration {max(0.001, nxt - t):.4f}"]
    if rec.frames:
        lines.append(f"file '{rec.frames[-1][1].resolve().as_posix()}'")
    lst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    first = rec.frames[0][0] if rec.frames else 0.0
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-vf", f"tpad=start_duration={first:.3f}:start_mode=clone,fps=30,scale=1920:1080,format=yuv420p",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-movflags", "+faststart",
                    str(out / "lasso-demo.mp4")], check=True)
    shutil.rmtree(out / "frames", ignore_errors=True)
    lst.unlink(missing_ok=True)


def stamp(t: float, srt: bool = True) -> str:
    h, rem = divmod(max(0.0, t), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",") if srt else f"{int(m)}:{s:04.1f}"


def write_captions(rec: Recorder, end: float, out: Path) -> None:
    srt, md = [], ["# Narration, timed to lasso-demo.mp4", "", "| Starts | Scene | Say |", "|---|---|---|"]
    for i, (s, t) in enumerate(rec.starts):
        nxt = rec.starts[i + 1][1] if i + 1 < len(rec.starts) else end
        srt += [str(i + 1), f"{stamp(t + 0.2)} --> {stamp(nxt - 0.2)}", s["line"], ""]
        md.append(f"| {stamp(t, False)} | {s['title']} | {s['line']} |")
    (out / "lasso-demo.srt").write_text("\n".join(srt), encoding="utf-8")
    (out / "narration.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("app", nargs="?", help="the app's URL")
    ap.add_argument("--key", help="the admin key")
    ap.add_argument("--out", default=str(HERE / "out"), help="where to write the video (default docs/video/out)")
    ap.add_argument("--pace", type=float, default=11.0, help="seconds per match minute (default 11)")
    ap.add_argument("--from-minute", type=int, default=77, help="where the replay starts (default 77)")
    ap.add_argument("--name", default="Brad", help="the demo fan's name (default Brad)")
    ap.add_argument("--script-only", action="store_true", help="write docs/video/SCRIPT.md and stop")
    a = ap.parse_args()
    write_script(HERE / "SCRIPT.md")
    if a.script_only:
        print(f"Wrote {HERE / 'SCRIPT.md'}")
        sys.exit(0)
    if not a.app or not a.key:
        ap.error("the app's URL and --key are needed to record")
    run(a.app.rstrip("/"), a.key, Path(a.out), a.pace, a.from_minute, a.name)
