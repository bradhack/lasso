"""Record Lasso's demo video from the live app, in sync with its narration script.

    python docs/video/record_demo.py https://<your app> --key <admin key>

It opens on the Lasso cover while it restarts the showcase match late in the second half (timed so the 82nd-minute
goal follows Call your shot, slowed down so each scene has time for its lines, with the VAR check as long as its
lines), signs in a demo fan of Eastholme Rangers, and drives a 1920x1080 browser through the scenes below: the Gauge,
Why it moved, Ask the Gaffer, Call your shot, the VAR check, the goal standing, Under the hood (enlarged, each round
highlighted as it's described), then four slides (Microsoft Fabric, a team of agents or one, how it's built, the
close). It captures the screen as it goes and writes, in docs/video/out/:

    lasso-demo.mp4   the video, 1080p: narrated by Azure AI Speech with --voice, otherwise silent for your own voice
    lasso-demo.srt   the narration as captions, timed to the video (read along, or upload to YouTube as captions)
    narration.md     each scene's start time and lines, to read from while you record

Every scene lasts at least as long as its lines take to say (about 2.4 words a second), and longer when the live
match makes it wait (an answer arriving, the goal, the agents' story). The script itself lives in SCENES below;
`--script-only` writes docs/video/SCRIPT.md from it without recording.

With --voice, each scene's lines are spoken by an Azure AI Speech neural voice (default en-US-JaneNeural
in its excited style, at +14%) on Lasso's own Foundry account, signed in as you through the Azure CLI. The lines are made first,
each scene lasts as long as its lines, and the voice is mixed in at each scene's start. Your account needs the
"Cognitive Services User" role on the Foundry account; if it's missing, the script prints the one command to add it.

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
import urllib.error
import urllib.request
from pathlib import Path

MATCH = "S5-MD07-03"  # the showcase: Eastholme Rangers 2-1 Brackenford City, Penke's winner at 82'
GOAL_CLOCK = 82.15    # when that goal goes in (and VAR checks it)
ADDED_1H = 3.08       # the first half's added time: replays count minutes from kickoff, including it
HERE = Path(__file__).resolve().parent
IMG = HERE.parent / "img"
WORDS_PER_SECOND = 2.9  # Azure AI Speech at the recorder's default rate

# The script: one entry per scene, in order. "line" is what you say; the scene lasts at least as long as it takes.
SCENES = [
    {"id": "intro", "title": "Lasso",
     "show": "Slide: the Lasso cover, while the showcase match restarts underneath.",
     "line": "This is Lasso. A team of AI agents watches live football with you, explains every shift in momentum, "
             "answers your questions, and lets you call what happens next."},
    {"id": "gauge", "title": "The Gaffer's Gauge",
     "show": "The live match: Eastholme Rangers 1-1 Brackenford City in the second half, Eastholme down to ten. "
             "The score and the Gauge glow.",
     "line": "We're following Eastholme Rangers: 1-1 late in the second half, down to ten men since an early red "
             "card, and our win probability model, the Gaffer, doesn't fancy their chances."},
    {"id": "why", "title": "Why it moved",
     "show": "Why it moved glows: the agents' latest story, in plain words.",
     "line": "Next, Why it moved. It explains what caused the win probability to change, in English, Spanish, "
             "Portuguese or French."},
    {"id": "ask", "title": "Ask the Gaffer",
     "show": "Typing \"Can Eastholme still win this?\" into Ask the Gaffer; the answer arrives with its AI agents chip.",
     "line": "Ask any question, at any time. One agent gathers the facts through the Model Context Protocol, and "
             "another writes your answer."},
    {"id": "callit", "title": "Call your shot",
     "show": "Call it: \"Eastholme Rangers score before 89'?\" Yes, then Lasso it.",
     "line": "Feeling brave? Call your shot. Biscuit rewards are set by the Gaffer's calculated odds, so long shots "
             "pay big. No money, just bragging rights."},
    {"id": "var", "title": "VAR check",
     "show": "82': Eastholme scores and VAR checks it. The VAR card shows the Gauge both ways; Call it asks "
             "\"Will the goal stand?\" and the fan picks It stands.",
     "line": "Eastholme scores! But VAR is checking it. The Gauge shows both outcomes, and a new call appears: "
             "will the goal stand? We say yes."},
    {"id": "goal", "title": "It stands",
     "show": "The goal stands: the Gauge jumps, both calls pay out, and the agents' story replaces the instant one.",
     "line": "It stands! The Gauge jumps, and both our calls win biscuits: Eastholme to score, and the goal to "
             "stand."},
    {"id": "hood", "title": "Under the hood",
     "show": "Under the hood for the goal's story, enlarged: round one (Stats, Gaffer), round two (Narrator, "
             "Persona, Game Master), then Checked by code, each highlighted in turn.",
     "line": "How did the agents write that story? Tap AI agents to look under the hood: two agents work out what "
             "changed, three more write the story, and our code checks every fact before you see it."},
    {"id": "fabric", "title": "Microsoft Fabric",
     "show": "Slide: the Lasso agents dashboard in Microsoft Fabric, panning down.",
     "line": "Everything streams into Microsoft Fabric, so we can track the agents' speed, cost and mistakes."},
    {"id": "compare", "title": "A team of agents or one",
     "show": "Slide: the Press Room team against one agent alone, on the same 27 questions.",
     "line": "Is a team of AI agents better than one? On the same 27 questions, the team passed them all, and a "
             "single agent missed two."},
    {"id": "arch", "title": "How it's built",
     "show": "Slide: how Lasso works, seven agents and one live pipeline.",
     "line": "Built on Microsoft Foundry and Agent Framework, over A2A and the Model Context Protocol, all running "
             "on Azure."},
    {"id": "close", "title": "Close",
     "show": "Slide: the Lasso cover.",
     "line": "That's Lasso. Watch smarter, call it first, and believe your call."},
]
for s in SCENES:
    s["min"] = round(len(s["line"].split()) / WORDS_PER_SECOND + 0.7, 1)


# ---------------------------------------------------------------- the script, as a document

def write_script(path: Path) -> None:
    total = sum(s["min"] for s in SCENES)
    out = ["# Lasso demo video: the script", "",
           f"About {total:.0f} seconds of narration (the recording runs a little longer while the live match plays). "
           "Generated from `docs/video/record_demo.py`, which records the video to match. With `--voice` it narrates "
           "these lines itself with an Azure AI Speech voice (Jane, excited, by default; `--sample-voices` says the "
           "opening and the VAR moment in about twenty voices so you can pick one, and `--style` and `--rate` change the "
           "delivery); without it, read them over the video, using `out/narration.md` for each scene's exact start "
           "time. The video must stay under two minutes.", "",
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
  font-family: 'DM Sans', system-ui, sans-serif; opacity: 0; transition: opacity .6s; pointer-events: none; }
#demo-slide.on { opacity: 1; }
#demo-slide h1 { font-family: 'Barlow Condensed', 'Arial Narrow', sans-serif; font-weight: 600; font-size: 68px;
  margin: 0; letter-spacing: .01em; }
#demo-slide .eyebrow { font-family: 'Barlow Condensed', 'Arial Narrow', sans-serif; font-weight: 600; font-size: 28px;
  letter-spacing: .12em; color: #C9A45C; }
.demo-big .sheet { align-items: center; }
.demo-big .sheet-inner.uth { max-width: 700px; zoom: 1.42; max-height: calc(92dvh / 1.42); border-radius: 28px; }
.uth .demo-glow { box-shadow: none !important; outline: 3px solid #C9A45C; outline-offset: 6px; border-radius: 18px; }
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
    if scene == "intro":
        return (f"<img src='{data_uri(IMG / 'submission-1-cover.png')}' style='position:absolute;inset:0;width:100%;"
                f"height:100%;object-fit:cover;animation:demo-zoom {d} ease-out forwards'>")
    if scene == "arch":
        return (f"<img src='{data_uri(IMG / 'submission-2-how-it-works.png')}' style='position:absolute;inset:0;"
                f"width:100%;height:100%;object-fit:cover;animation:demo-zoom {d} ease-out forwards'>")
    return (f"<img src='{data_uri(IMG / 'submission-1-cover.png')}' style='position:absolute;inset:0;width:100%;"
            f"height:100%;object-fit:cover;animation:demo-zoom {d} ease-out forwards'>")


# ---------------------------------------------------------------- the narration voice (Azure AI Speech)

# How the voice should say what's written for readers.
SAY = [("A2A", "A to A"), ("MCP", "M C P"), ("Cosmos DB", "Cosmos D B"), ("Web PubSub", "Web Pub Sub"),
       ("AI ", "A I "), ("Lasso:", "Lasso."), ("27/27", "27 of 27"), ("1-1", "one all"), ("VAR", "V A R")]

# Voices worth hearing for the narration, with a speaking style where the voice has one (--sample-voices).
# Styles change the delivery; a voice without that style just reads normally.
SAMPLE_VOICES = [
    ("en-US-AndrewMultilingualNeural", None),     # warm, natural (the default)
    ("en-US-AndrewMultilingualNeural", "excited"),  # the same, asked for excited (read normally if it has no styles)
    ("en-US-BrianMultilingualNeural", None),      # brighter, younger
    ("en-US-Andrew:DragonHDLatestNeural", None),  # HD: the most expressive, in some regions only
    ("en-US-Davis:DragonHDLatestNeural", None),   # HD, deeper
    ("en-US-DavisNeural", "excited"),             # big, sporty
    ("en-US-DavisNeural", "cheerful"),            # Davis, a notch calmer
    ("en-US-DavisNeural", "shouting"),            # Davis, a notch louder
    ("en-US-GuyNeural", "excited"),
    ("en-US-TonyNeural", "excited"),              # energetic
    ("en-US-JasonNeural", "excited"),
    ("en-US-GuyNeural", "newscast"),              # classic announcer
    ("en-US-JaneNeural", "excited"),              # women's voices with the same excited style
    ("en-US-NancyNeural", "excited"),
    ("en-US-AriaNeural", "excited"),
    ("en-US-SaraNeural", "excited"),
    ("en-US-ChristopherNeural", None),            # deep, steady
    ("en-US-SteffanNeural", None),
]


def _cli(*args: str) -> str:
    exe = shutil.which(args[0])
    if not exe:
        sys.exit(f"{args[0]} isn't on the PATH; it's needed for --voice (sign in with `az login`).")
    r = subprocess.run([exe, *args[1:]], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"`{' '.join(args)}` failed: {r.stderr.strip()[:400]}")
    return r.stdout.strip()


def speech_account(resource_group: str | None) -> tuple[str, str]:
    """Lasso's Foundry account (it hosts Azure AI Speech): its resource id and region."""
    rg = resource_group or _cli("azd", "env", "get-value", "AZURE_RESOURCE_GROUP")
    acct = json.loads(_cli("az", "cognitiveservices", "account", "list", "-g", rg,
                           "--query", "[?kind=='AIServices'] | [0].{id:id, location:location}", "-o", "json") or "null")
    if not acct:
        sys.exit(f"No Foundry (AIServices) account found in resource group {rg}; pass --resource-group.")
    return acct["id"], acct["location"]


def ssml_for(text: str, voice: str, style: str | None, rate: str) -> str:
    for a, b in SAY:
        text = text.replace(a, b)
    text = text.replace("&", "and").replace("<", "").replace(">", "")
    if rate and rate not in ("0%", "+0%"):
        text = f"<prosody rate='{rate}'>{text}</prosody>"
    if style:
        text = f"<mstts:express-as style='{style}'>{text}</mstts:express-as>"
    return (f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' "
            f"xmlns:mstts='https://www.w3.org/2001/mstts' xml:lang='en-US'><voice name='{voice}'>{text}</voice></speak>")


def synthesize(lines: list[str], voice: str, resource_id: str, region: str, folder: Path,
               style: str | None = None, rate: str = "+14%", names: list[str] | None = None,
               skip_unknown: bool = False) -> list[Path]:
    token = _cli("az", "account", "get-access-token", "--resource", "https://cognitiveservices.azure.com",
                 "--query", "accessToken", "-o", "tsv")
    folder.mkdir(parents=True, exist_ok=True)
    files = []
    for i, line in enumerate(lines):
        ssml = ssml_for(line, voice, style, rate)
        req = urllib.request.Request(
            f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1", data=ssml.encode("utf-8"),
            method="POST", headers={"Authorization": f"Bearer aad#{resource_id}#{token}",
                                    "Content-Type": "application/ssml+xml", "User-Agent": "lasso-demo",
                                    "X-Microsoft-OutputFormat": "audio-48khz-192kbitrate-mono-mp3"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                audio = r.read()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                me = _cli("az", "ad", "signed-in-user", "show", "--query", "id", "-o", "tsv")
                sys.exit("Azure AI Speech refused your sign-in. Give your account the Cognitive Services User role on "
                         "the Foundry account, wait a few minutes, then run this again:\n\n"
                         f'  az role assignment create --assignee {me} --role "Cognitive Services User" '
                         f'--scope "{resource_id}"\n')
            if e.code == 400:
                if skip_unknown:
                    return []
                sys.exit(f"Azure AI Speech rejected the voice {voice!r} (or the style {style!r}); pick another.")
            raise
        path = folder / (names[i] if names else f"{i + 1:02d}.mp3")
        path.write_bytes(audio)
        files.append(path)
    return files


def sample_voices(out: Path, resource_group: str | None, rate: str) -> None:
    """Say the opening and the VAR moment in each voice in SAMPLE_VOICES, to pick one by ear."""
    resource_id, region = speech_account(resource_group)
    folder = out / "voices"
    shutil.rmtree(folder, ignore_errors=True)
    lines = [next(s["line"] for s in SCENES if s["id"] == "intro"),
             next(s["line"] for s in SCENES if s["id"] == "var")]
    text = " ".join(lines)
    print(f"Voice samples ({region}), in {folder}:")
    for voice, style in SAMPLE_VOICES:
        name = voice.replace(":", "-") + (f"-{style}" if style else "") + ".mp3"
        made = synthesize([text], voice, resource_id, region, folder, style, rate, [name], skip_unknown=True)
        print(f"  {name:48s}" + ("" if made else "  (not available in this region)"))
    print("\nRecord with the one you like, for example:\n"
          "  python docs/video/record_demo.py <app> --key <key> --voice en-US-DavisNeural --style excited")


def preview_voice(out: Path, voice: str, style: str | None, rate: str, resource_group: str | None) -> None:
    """The whole narration in one voice, scene after scene, with the pauses the video has between scenes."""
    resource_id, region = speech_account(resource_group)
    tag = voice.replace(":", "-") + (f"-{style}" if style else "")
    folder = out / "preview" / tag
    shutil.rmtree(folder, ignore_errors=True)
    clips = synthesize([s["line"] for s in SCENES], voice, resource_id, region, folder, style, rate)
    lst = folder / "list.txt"
    gap = folder / "gap.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "0.6",
                    "-b:a", "192k", str(gap)], check=True)
    lst.write_text("".join(f"file '{c.resolve().as_posix()}'\nfile '{gap.resolve().as_posix()}'\n" for c in clips),
                   encoding="utf-8")
    final = out / f"narration-{tag}.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c:a", "libmp3lame", "-b:a", "192k", str(final)], check=True)
    secs = duration(final)
    print(f"{final}  ({secs:.0f} seconds of narration; the video adds about 15 for the live match)")


def duration(path: Path) -> float:
    r = subprocess.run([shutil.which("ffprobe") or "ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def mix_voice(rec: "Recorder", out: Path, clips: list[Path]) -> None:
    """Lay each scene's clip in at its start (a beat after the cut), under the silent video."""
    silent = out / "lasso-demo-silent.mp4"
    (out / "lasso-demo.mp4").replace(silent)
    args = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent)]
    chains, labels = [], []
    for i, ((scene, start), clip) in enumerate(zip(rec.starts, clips)):
        args += ["-i", str(clip)]
        ms = int((start + 0.35) * 1000)
        chains.append(f"[{i + 1}:a]adelay={ms}:all=1,aresample=48000[a{i}]")
        labels.append(f"[a{i}]")
    graph = ";".join(chains) + f";{''.join(labels)}amix=inputs={len(labels)}:normalize=0,alimiter=limit=0.95,apad[voice]"
    args += ["-filter_complex", graph, "-map", "0:v", "-map", "[voice]", "-c:v", "copy", "-c:a", "aac",
             "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out / "lasso-demo.mp4")]
    subprocess.run(args, check=True)


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


def glow(rec: Recorder, selector: str | None, index: int = 0, scroll: bool = False) -> None:
    """Highlight one element (the index-th match of the selector), scrolling it into view if asked."""
    rec.page.evaluate("([sel, i, scroll]) => { document.querySelectorAll('.demo-glow')"
                      ".forEach(e => e.classList.remove('demo-glow')); if (!sel) return;"
                      " const e = document.querySelectorAll(sel)[i]; if (!e) return; e.classList.add('demo-glow');"
                      " if (scroll) e.scrollIntoView({ behavior: 'smooth', block: 'center' }); }",
                      [selector, index, scroll])


def hide_slide(rec: Recorder) -> None:
    rec.page.evaluate("() => { const s = document.getElementById('demo-slide'); if (s) s.classList.remove('on'); }")
    rec.wait(0.6)


def show_slide(rec: Recorder, scene: dict) -> None:
    html = slide_html(scene["id"], scene["min"])
    rec.page.evaluate("(html) => { let s = document.getElementById('demo-slide'); if (!s) { s = document.createElement('div');"
                      " s.id = 'demo-slide'; document.body.appendChild(s); } s.classList.remove('on'); s.innerHTML = html;"
                      " requestAnimationFrame(() => requestAnimationFrame(() => s.classList.add('on'))); }", html)


def run(app: str, key: str, out: Path, pace: float, from_minute: float | None, name: str = "Brad",
        voice: str | None = None, resource_group: str | None = None, style: str | None = None,
        rate: str = "+14%") -> None:
    from playwright.sync_api import sync_playwright

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg isn't on the PATH. On Windows: winget install Gyan.FFmpeg (then open a new terminal).")
    out.mkdir(parents=True, exist_ok=True)
    try:  # the short VAR check and the demo's call need the API from October 18 or later
        paths = http(app, "GET", "/openapi.json")["paths"]
        params = paths["/api/admin/matches/{match_id}/restart"]["post"].get("parameters", [])
        if not any(prm.get("name") == "var_seconds" for prm in params) \
                or "/api/admin/matches/{match_id}/call" not in paths:
            sys.exit("The app's API is older than this recorder (it needs the short VAR check and the demo's own "
                     "Call your shot). Run `azd deploy api`, then record again.")
    except (KeyError, urllib.error.URLError):
        pass
    clips: list[Path] = []
    if voice:  # the lines first: each scene then lasts as long as its voice
        resource_id, region = speech_account(resource_group)
        print(f"Narrating with {voice}{f' ({style})' if style else ''} (Azure AI Speech, {region})...")
        clips = synthesize([s["line"] for s in SCENES], voice, resource_id, region, out / "voice", style, rate)
        for s, clip in zip(SCENES, clips):
            s["min"] = round(duration(clip) + 0.5, 2)
        print(f"  {sum(s['min'] for s in SCENES):.0f} seconds of narration")
    frames_dir = out / "frames"
    shutil.rmtree(frames_dir, ignore_errors=True)
    frames_dir.mkdir()
    sec = {s["id"]: s["min"] for s in SCENES}

    # Start the match so the goal goes in just after Call your shot: the scenes before it, plus time for the
    # Gaffer's answer and a little to spare. The intro plays over the restart.
    lead = sec["gauge"] + sec["why"] + sec["ask"] + 4.0 + 1.0 + sec["callit"] + 2.0
    start = from_minute if from_minute is not None else round(GOAL_CLOCK - lead / pace, 2)
    var_seconds = round(min(60.0, max(4.0, sec["var"] + 1.0)), 1)

    match = http(app, "GET", f"/api/matches/{MATCH}")
    home = match["home"]
    user = http(app, "POST", "/api/users", {"name": name[:24], "club_id": home["club_id"]})
    http(app, "PATCH", f"/api/users/{user['id']}", {"lang": "en", "persona": "fan"})
    print(f"Demo fan {user['id']} supports {home['name']}. The match restarts at {start:.1f}' (goal at "
          f"{GOAL_CLOCK:g}'), {pace:g} seconds a minute, VAR check {var_seconds:g} seconds.")

    def clock() -> float:
        try:
            m = http(app, "GET", f"/api/matches/{MATCH}")
            return float(m.get("clock") or 0) if m.get("period") == 2 else 0.0
        except Exception:  # noqa: BLE001
            return 0.0

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        ctx.add_init_script(f"try {{ localStorage.setItem('lasso.user', {json.dumps(user['id'])}); }} catch (e) {{}}")
        page = ctx.new_page()
        page.goto(f"{app}/#/match/{MATCH}")
        page.add_style_tag(content=OVERLAY_CSS)
        page.evaluate("() => { const c = document.createElement('div'); c.id = 'demo-cursor';"
                      " document.body.appendChild(c); }")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:  # noqa: BLE001
            pass  # a live page may never go quiet; it has loaded

        rec = Recorder(page, ctx.new_cdp_session(page), frames_dir)
        rec.start()
        print("Recording:")

        s = rec.scene("intro")  # the cover, while the match restarts underneath it
        show_slide(rec, s)
        rec.wait(0.8)
        begin = start - max(0.0, s["min"] - 2.0) / pace  # so the match reaches `start` as the intro ends
        http(app, "POST", f"/api/admin/matches/{MATCH}/restart?from_minute={begin + ADDED_1H:.2f}"
                          f"&minute_seconds={pace}&var_seconds={var_seconds}", {}, key)
        rec.hold(s)
        deadline = time.monotonic() + 30
        while not (start - 0.1 <= clock() <= start + 2.0) and time.monotonic() < deadline:
            rec.wait(0.5)  # until the restarted match reaches the start (not the old one still playing)
        page.wait_for_selector(".card.why", timeout=30000)
        hide_slide(rec)

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
        box.type("Can Eastholme still win this?", delay=60)
        rec.wait(0.3)
        cursor_to(rec, page.locator(".card.ask button.cta"))
        try:
            page.wait_for_selector(".card.ask .bubble.gaffer:not(.thinking)", timeout=40000)
        except Exception:  # noqa: BLE001
            print("    (the answer took over 40 seconds; carrying on)")
        rec.hold(s)
        rec.wait(0.5)  # time to read the answer

        s = rec.scene("callit")
        glow(rec, "section.callit")
        try:  # the call the script is about, opened now (the Game Master may have picked another)
            http(app, "POST", f"/api/admin/matches/{MATCH}/call?team=0", {}, key)
        except Exception as e:  # noqa: BLE001
            print(f"    (couldn't open the Eastholme-to-score call: {e})")
        try:
            page.wait_for_function("() => { const t = document.querySelector('section.callit')?.innerText || '';"
                                   " return /Eastholme/.test(t) && /score before/i.test(t); }", timeout=5000)
        except Exception:  # noqa: BLE001
            print("    (no Eastholme-to-score call on screen; using the one open now)")
        callit = page.locator("section.callit")
        callit.scroll_into_view_if_needed()
        rec.wait(0.6)
        yes = callit.locator("button.opt").first
        if yes.count():
            cursor_to(rec, yes)
            lasso = callit.locator("button.cta")
            if lasso.count() and lasso.is_enabled():
                cursor_to(rec, lasso)
        rec.hold(s)

        deadline = time.monotonic() + 90  # the goal goes in and VAR checks it
        while time.monotonic() < deadline and not page.locator(".card.var.checking").count():
            try:
                if (http(app, "GET", f"/api/matches/{MATCH}").get("score") or [0, 0])[0] >= 2:
                    print("    (the VAR check had already ended: the goal stood before Call your shot finished)")
                    break
            except Exception:  # noqa: BLE001
                pass
            rec.wait(0.3)
        s = rec.scene("var")
        page.evaluate("() => { const v = document.querySelector('.card.var'); if (v) window.scrollTo({ top: "
                      "Math.max(0, v.getBoundingClientRect().top + window.scrollY - 90), behavior: 'smooth' }); }")
        glow(rec, ".card.var")
        rec.wait(1.2)
        try:  # the quick call jumps the queue: will the goal stand?
            page.wait_for_function("() => /stand/i.test(document.querySelector('section.callit')?.innerText || '')",
                                   timeout=5000)
            stands = page.locator("section.callit button.opt", has_text="stands")
            if stands.count():
                glow(rec, "section.callit")
                cursor_to(rec, stands.first)
                lasso = page.locator("section.callit button.cta")
                if lasso.count() and lasso.is_enabled():
                    cursor_to(rec, lasso)
        except Exception:  # noqa: BLE001
            print("    (the VAR call didn't open in time)")
        rec.hold(s)

        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:  # until VAR's decision is in and the goal stands
            try:
                if (http(app, "GET", f"/api/matches/{MATCH}").get("score") or [0, 0])[0] >= 2:
                    break
            except Exception:  # noqa: BLE001
                pass
            rec.wait(0.4)
        else:
            print("    (the goal hadn't stood within a minute)")
        page.wait_for_timeout(300)  # the page gets the goal a moment after the API
        s = rec.scene("goal")
        page.evaluate("() => window.scrollTo({ top: 0, behavior: 'smooth' })")
        glow(rec, ".app.wide section.card")
        rec.wait(min(3.0, s["min"] / 2))
        glow(rec, ".card.why", scroll=True)
        rec.hold(s)
        try:  # the agents' story for the goal: Why it moved gets its "AI agents" chip
            page.wait_for_function("() => { const w = document.querySelector('.card.why');"
                                   " return w && /82'/.test(w.innerText) && w.querySelector('.chip.agents'); }",
                                   timeout=30000, polling=500)
        except Exception:  # noqa: BLE001
            print("    (the agents' story for the goal hadn't arrived after 30 seconds; using the latest one)")

        s = rec.scene("hood")
        glow(rec, None)
        page.evaluate("() => document.body.classList.add('demo-big')")
        chip = page.locator(".card.why .chip.agents")
        if not chip.count():
            chip = page.locator(".chip.agents")
        if chip.count():
            cursor_to(rec, chip.first)
            page.wait_for_selector(".sheet .uth", timeout=10000)
            # In step with the words: round one, round two, then what the code checked.
            for at, sel, i in ((0.22, ".uth-stage", 0), (0.50, ".uth-stage", 1), (0.74, ".uth-checks", 0)):
                start_t = next(t for x, t in rec.starts if x is s)
                left = start_t + s["min"] * at - rec.now()
                if left > 0:
                    rec.wait(left)
                glow(rec, sel, i, scroll=True)
        else:
            print("    (no AI agents chip on screen)")
        rec.hold(s)
        if page.locator(".sheet").count():
            glow(rec, None)
            cursor_to(rec, page.locator(".sheet .uth button.cta"))

        for scene_id in ("fabric", "compare", "arch", "close"):
            s = rec.scene(scene_id)
            show_slide(rec, s)
            rec.hold(s)
        rec.wait(0.5)
        end = rec.now()
        rec.stop()
        browser.close()

    encode(rec, end, out)
    write_captions(rec, end, out)
    if clips:
        mix_voice(rec, out, clips)
        print(f"\nDone: {out / 'lasso-demo.mp4'} ({end:.0f} seconds, narrated), lasso-demo-silent.mp4, "
              "lasso-demo.srt and narration.md.")
    else:
        print(f"\nDone: {out / 'lasso-demo.mp4'} ({end:.0f} seconds), with lasso-demo.srt and narration.md.")
    if end > 119:
        print("It's over two minutes: the live match made some scenes wait. Run it again, or trim the wait before "
              "Under the hood in a video editor.")


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
    ap.add_argument("--from-minute", type=float, default=None,
                    help="the minute recording starts at (default: worked out so the goal follows Call your shot)")
    ap.add_argument("--name", default="Brad", help="the demo fan's name (default Brad)")
    ap.add_argument("--voice", nargs="?", const="en-US-JaneNeural", default=None,
                    help="narrate with an Azure AI Speech voice (default en-US-JaneNeural; hear others with "
                         "--sample-voices)")
    ap.add_argument("--style", default="excited",
                    help="the voice's speaking style, for voices that have one (default excited; also newscast, "
                         "cheerful; none for no style)")
    ap.add_argument("--rate", default="+14%", help="speaking rate, e.g. +10%% or -5%% (default +14%%)")
    ap.add_argument("--sample-voices", action="store_true",
                    help="say the opening and the VAR moment in about twenty voices, into docs/video/out/voices, and stop")
    ap.add_argument("--preview", action="store_true",
                    help="say the whole script in the --voice (and --style) into docs/video/out, without recording")
    ap.add_argument("--resource-group", help="where Lasso's Foundry account is (default: from azd)")
    ap.add_argument("--script-only", action="store_true", help="write docs/video/SCRIPT.md and stop")
    a = ap.parse_args()
    if a.style and a.style.lower() == "none":
        a.style = None
    write_script(HERE / "SCRIPT.md")
    if a.script_only:
        print(f"Wrote {HERE / 'SCRIPT.md'}")
        sys.exit(0)
    if a.sample_voices:
        sample_voices(Path(a.out), a.resource_group, a.rate)
        sys.exit(0)
    if a.preview:
        preview_voice(Path(a.out), a.voice or "en-US-JaneNeural", a.style, a.rate, a.resource_group)
        sys.exit(0)
    if not a.app or not a.key:
        ap.error("the app's URL and --key are needed to record")
    run(a.app.rstrip("/"), a.key, Path(a.out), a.pace, a.from_minute, a.name, a.voice, a.resource_group,
        a.style, a.rate)
