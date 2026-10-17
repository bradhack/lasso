import { useEffect, useMemo, useRef, useState } from "react";
import { t } from "../i18n";
import { useStore } from "../store";
import type { Lang, MatchSnapshot, Touch } from "../types";
import { Crest } from "./bits";

/**
 * Touchline: the ball, live, on a 105 x 68 m pitch. Home attacks left to right.
 * Touches arrive in small batches with each Gauge update; we replay them one by one so the ball
 * travels pass by pass instead of jumping.
 */

const W = 105;
const H = 68;
const TEAM = ["var(--home)", "var(--away)"];
const KEY = "lasso-touchline-hidden";
const VIEW_KEY = "lasso-touchline-view";
const GROUND_PASS = 18; // metres: shorter passes are played along the ground and drawn nearly straight
const CHAIN_MS = 7000; // how long a goal's build-up stays on the pitch
const TRAIL = 7; // dots in the ball's comet tail
const reduceMotion = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

function readPref(key: string) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function readHidden() {
  return readPref(KEY) === "1";
}

export function Touchline({ snap, lang }: { snap: MatchSnapshot; lang: Lang }) {
  const touches = snap.touches ?? [];
  const [hidden, setHidden] = useState(readHidden);
  const [cursor, setCursor] = useState(() => touches[touches.length - 1]?.s ?? 0);
  const latestSeq = touches[touches.length - 1]?.s ?? 0;
  const timer = useRef<number | undefined>(undefined);

  // Step the cursor through newly arrived touches. Faster when a backlog builds; jump if it is long.
  useEffect(() => {
    if (latestSeq <= cursor) {
      if (latestSeq < cursor) setCursor(latestSeq); // the match restarted
      return;
    }
    const backlog = touches.filter((x) => x.s > cursor);
    if (reduceMotion || hidden || backlog.length > 10) {
      setCursor(latestSeq);
      return;
    }
    const delay = Math.max(90, Math.min(320, 900 / backlog.length));
    timer.current = window.setTimeout(() => setCursor(backlog[0].s), delay);
    return () => window.clearTimeout(timer.current);
  }, [latestSeq, cursor, hidden]); // eslint-disable-line react-hooks/exhaustive-deps

  const shown = useMemo(() => touches.filter((x) => x.s <= cursor), [touches, cursor]);
  const last = shown[shown.length - 1];
  const shots = useMemo(() => (snap.shots ?? []).filter((x) => x.s <= cursor), [snap.shots, cursor]);
  const passes = currentMove(shown);
  const markers = shown.filter((x) => ["tackle", "interception", "save", "corner", "foul"].includes(x.t) && x.x !== undefined).slice(-6);
  const ball = ballAt(last);
  // On a shot the shooting side still has the ball on screen; the restart flips it on the next touch.
  const possession = last?.t === "shot" ? last.k : last?.pos ?? snap.possession ?? null;
  // Hold the goal moment on screen for a few seconds, even as the restart comes in.
  const lastGoal = useMemo(() => [...shown].reverse().find((x) => x.t === "shot" && x.g), [shown]);
  const [flash, setFlash] = useState<Touch | null>(null);
  const seenGoal = useRef(lastGoal?.s ?? 0);
  useEffect(() => {
    if (!lastGoal || lastGoal.s <= seenGoal.current) return;
    seenGoal.current = lastGoal.s;
    if (touches.slice(-8).every((x) => x.s !== lastGoal.s)) return; // an old goal caught up in a replay: no fanfare
    setFlash(lastGoal);
    const tm = window.setTimeout(() => setFlash(null), 3500);
    return () => window.clearTimeout(tm);
  }, [lastGoal?.s]); // eslint-disable-line react-hooks/exhaustive-deps

  const persona = useStore((s) => s.user?.persona);
  // A saved choice wins; otherwise analysts open on the shot map and fans on the live ball.
  const [view, setView] = useState<"live" | "shots">(() => {
    const saved = readPref(VIEW_KEY);
    return saved === "shots" || saved === "live" ? saved : persona === "analyst" ? "shots" : "live";
  });
  const [picked, setPicked] = useState<number | null>(null);
  const recentShot = [...shown.slice(-8)].reverse().find((x) => x.t === "shot");
  const selected = shots.find((x) => x.s === picked) ?? shots[shots.length - 1];

  // How it was built: after a goal or big chance arrives live, its passing move stays on the pitch for a few
  // seconds (on the shot map, the picked shot's move shows for as long as it's picked).
  const [replayed, setReplayed] = useState<Touch | null>(null);
  const seenChain = useRef(recentShot?.s ?? 0);
  useEffect(() => {
    const x = recentShot;
    if (!x || !x.chain?.passes.length || x.s <= seenChain.current) return;
    seenChain.current = x.s;
    if (touches.slice(-8).every((y) => y.s !== x.s)) return; // caught up from earlier: no replay
    setReplayed(x);
    const tm = window.setTimeout(() => setReplayed(null), CHAIN_MS);
    return () => window.clearTimeout(tm);
  }, [recentShot?.s]); // eslint-disable-line react-hooks/exhaustive-deps
  const chainShot = view === "shots" ? (selected?.chain?.passes.length ? selected : null) : replayed;

  const toggle = () => {
    const next = !hidden;
    setHidden(next);
    writePref(KEY, next ? "1" : "0");
  };
  const choose = (v: "live" | "shots") => {
    setView(v);
    writePref(VIEW_KEY, v);
  };

  return (
    <section className="card touchline" aria-label={t("touchline", lang)}>
      <div className="row">
        <span className="eyebrow gold">{t("touchline", lang)}</span>
        <div className="row" style={{ gap: 8 }}>
          {!hidden && (
            <div className="seg mini" role="tablist">
              <button role="tab" aria-selected={view === "live"} className={`tab${view === "live" ? " sel" : ""}`} onClick={() => choose("live")}>{t("live", lang)}</button>
              <button role="tab" aria-selected={view === "shots"} className={`tab${view === "shots" ? " sel" : ""}`} onClick={() => choose("shots")}>{t("vShots", lang)}</button>
            </div>
          )}
          <button className="linkbtn" onClick={toggle} aria-expanded={!hidden}>
            {hidden ? t("show", lang) : t("hide", lang)}
          </button>
        </div>
      </div>
      {!hidden && (
        <>
          <svg className="pitch" viewBox={`-3 -3 ${W + 6} ${H + 6}`} role="group"
            aria-label={view === "live" ? (last ? describe(last, snap, lang) : t("touchline", lang)) : t("vShots", lang)}>
            <PitchMarkings />
            {view === "live" && (
              <>
                {recentShot && <ShotDot s={recentShot} now={recentShot.s === last?.s} />}
                {markers.map((m, i) => (
                  <Marker key={`m-${m.s}`} m={m} age={markers.length - 1 - i} />
                ))}
                {!chainShot && passes.map((p, i) => {
                  // A gap between where the last pass arrived and where this one starts is a run with the ball.
                  const prev = passes[i - 1];
                  const carry = prev && prev.ex !== undefined && prev.ey !== undefined && p.x !== undefined && p.y !== undefined
                    && Math.hypot(p.x - prev.ex, p.y - prev.ey) > 3;
                  return (
                    <g key={`p-${p.s}`} className="fresh" style={{ ["--team" as string]: TEAM[p.k] }}>
                      {carry && <line x1={prev.ex} y1={prev.ey} x2={p.x} y2={p.y} className="carry" />}
                      <path d={taperedPass(p)} className={`pass${p.o ? "" : " cut"}`} />
                    </g>
                  );
                })}
                {chainShot && <Chain shot={chainShot} />}
                {ball && <Ball last={last} at={ball} fill={TEAM[possession ?? last?.k ?? 0]} />}
              </>
            )}
            {view === "shots" && chainShot && <Chain shot={chainShot} still />}
            {view === "shots" && shots.map((x) => (
              <g key={`shot-${x.s}`} className="shot-hit" onClick={() => setPicked(x.s)} role="button" tabIndex={0}
                aria-label={`${x.m}' ${describe(x, snap, lang)}`} aria-pressed={x.s === selected?.s}
                onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), setPicked(x.s))}>
                <ShotDot s={x} now={x.s === last?.s} picked={x.s === selected?.s} />
                <circle cx={x.x} cy={x.y} r="4.5" className="hit" />
              </g>
            ))}
            {flash && (
              <g key={`goal-${flash.s}`} className="goalflash">
                <circle cx={flash.k === 0 ? W : 0} cy={H / 2} r="6" />
                <text x={W / 2} y={H / 2 + 4} textAnchor="middle">{t("tGoal", lang)}</text>
              </g>
            )}
          </svg>
          {view === "live" ? (
            <>
            <div className="pitch-foot">
              <span className="dir"><Crest club={snap.home} size="sm" />{snap.home.short} <b>→</b></span>
              <span className="ticker" aria-live="polite">
                {possession !== null && snap.status !== "scheduled" && <i className="possdot" style={{ background: TEAM[possession] }} />}
                {last ? `${last.m}'  ${describe(last, snap, lang)}` : ""}
              </span>
              <span className="dir right"><b>←</b> {snap.away.short}<Crest club={snap.away} size="sm" /></span>
            </div>
            {chainShot && <p className="built-cap" aria-live="polite">{builtText(chainShot, lang)}</p>}
            {/* What the marks on the pitch are: tackles drawn as a cross read as missed shots without a key. */}
            <div className="mk-key" aria-hidden="true">
              <span><svg viewBox="-3 -3 6 6"><circle r="2" className="kball" /></svg>{t("kBall", lang)}</span>
              <span><svg viewBox="-3 -3 6 6"><path d="M-1.6 -1.6L1.6 1.6M1.6 -1.6L-1.6 1.6" /></svg>{t("kTackle", lang)}</span>
              <span><svg viewBox="-3 -3 6 6"><path d="M0 -1.9L1.9 0L0 1.9L-1.9 0Z" /></svg>{t("kInterception", lang)}</span>
              <span><svg viewBox="-3 -4 6 8"><rect x="-1.4" y="-3.2" width="2.8" height="6.4" rx="1" /></svg>{t("kSave", lang)}</span>
              <span><svg viewBox="-1 -5 6 6"><path d="M0 0V-4.5L3 -3.4L0 -2.3" /></svg>{t("kCorner", lang)}</span>
            </div>
            </>
          ) : (
            <div className="shotfoot">
              <div className="legend">
                <span><i className="lg goal" />{t("goalWord", lang)}</span>
                <span><i className="lg on" />{t("onTarget", lang)}</span>
                <span><i className="lg off" />{t("tOff", lang)}</span>
                <span className="muted">{t("sizeXg", lang)}</span>
              </div>
              {[0, 1].map((k) => {
                const mine = shots.filter((x) => x.k === k);
                const club = k === 0 ? snap.home : snap.away;
                return (
                  <div key={k} className="shotrow">
                    <span className="who"><Crest club={club} size="sm" /><b>{club.short}</b></span>
                    <span><b>{mine.length}</b>{t("vShots", lang).toLowerCase()}</span>
                    <span><b>{mine.filter((x) => x.on || x.g).length}</b>{t("onTarget", lang)}</span>
                    <span><b>{mine.reduce((a, x) => a + (x.xg ?? 0), 0).toFixed(2)}</b>xG</span>
                    <span><b>{mine.filter((x) => x.g).length}</b>{t("goalsWord", lang)}</span>
                  </div>
                );
              })}
              {selected && (
                <div className="shotpick" aria-live="polite">
                  <i style={{ background: TEAM[selected.k] }} />
                  {selected.m}' {describe(selected, snap, lang)}
                  {selected.chain?.passes.length ? <span className="built">{builtText(selected, lang)}</span> : null}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}

/**
 * A pass drawn the way the ball travels: a short pass along the ground stays nearly straight, a long ball
 * (a switch, a cross, a ball over the top) arcs like it's lofted. The side of the bend is fixed per pass (so it
 * never flickers) and flipped when it would leave the pitch.
 */
function passCurve(p: Touch): { c: [number, number]; d: string } {
  const x1 = p.x ?? 0, y1 = p.y ?? 0, x2 = p.ex ?? x1, y2 = p.ey ?? y1;
  const dx = x2 - x1, dy = y2 - y1;
  const len = Math.hypot(dx, dy) || 1;
  const bend = len < GROUND_PASS ? len * 0.04 : Math.min(9, len * 0.04 + (len - GROUND_PASS) * 0.28);
  const mx = (x1 + x2) / 2, my = (y1 + y2) / 2, nx = -dy / len, ny = dx / len;
  let side = p.s % 2 ? 1 : -1;
  let cx = mx + nx * bend * side, cy = my + ny * bend * side;
  if (cx < 1 || cx > W - 1 || cy < 1 || cy > H - 1) {
    side = -side;
    cx = mx + nx * bend * side;
    cy = my + ny * bend * side;
  }
  const r = (v: number) => Math.round(v * 10) / 10;
  return { c: [cx, cy], d: `M${r(x1)} ${r(y1)}Q${r(cx)} ${r(cy)} ${r(x2)} ${r(y2)}` };
}

/**
 * The ball, with a short comet tail. When a pass starts away from where the ball is, the player ran with it
 * first: the ball glides there along the ground, then travels along the pass's own curve, slowing as it arrives.
 */
function Ball({ last, at, fill }: { last?: Touch; at: [number, number]; fill: string }) {
  const g = useRef<SVGGElement>(null);
  const tail = useRef<(SVGCircleElement | null)[]>([]);
  const pos = useRef<[number, number] | null>(null);
  const hist = useRef<[number, number][]>([]);
  useEffect(() => {
    const el = g.current;
    if (!el) return;
    const draw = (q: [number, number]) => {
      pos.current = q;
      el.setAttribute("transform", `translate(${q[0].toFixed(2)} ${q[1].toFixed(2)})`);
      hist.current = [q, ...hist.current].slice(0, TRAIL * 2);
      tail.current.forEach((c, i) => {
        const h = hist.current[(i + 1) * 2] ?? q;
        c?.setAttribute("cx", h[0].toFixed(2));
        c?.setAttribute("cy", h[1].toFixed(2));
      });
    };
    const from = pos.current;
    if (!from || reduceMotion || (from[0] === at[0] && from[1] === at[1])) {
      hist.current = [];
      draw(at);
      for (let i = 0; i < TRAIL * 2; i++) draw(at); // no tail at rest
      return;
    }
    const pass = last?.t === "pass" && last.ex !== undefined ? last : null;
    const c = pass ? passCurve(pass).c : null;
    const kick: [number, number] | null = pass && pass.x !== undefined && pass.y !== undefined
      && Math.hypot(pass.x - from[0], pass.y - from[1]) > 3 ? [pass.x, pass.y] : null;
    const runMs = kick ? 220 : 0;
    const flyMs = c ? 320 : 240;
    const settle = 160; // the tail catches up after the ball stops
    const t0 = performance.now();
    let raf = 0;
    const step = (now: number) => {
      const ms = now - t0;
      if (kick && ms < runMs) {
        const u = ms / runMs; // a steady run with the ball
        draw([from[0] + (kick[0] - from[0]) * u, from[1] + (kick[1] - from[1]) * u]);
      } else {
        const s0 = kick ?? from;
        const u = Math.min(1, (ms - runMs) / flyMs);
        const e = 1 - (1 - u) * (1 - u);
        const a = 1 - e;
        draw(c
          ? [a * a * s0[0] + 2 * a * e * c[0] + e * e * at[0], a * a * s0[1] + 2 * a * e * c[1] + e * e * at[1]]
          : [s0[0] + (at[0] - s0[0]) * e, s0[1] + (at[1] - s0[1]) * e]);
      }
      if (ms < runMs + flyMs + settle) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [at[0], at[1], last?.s]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <>
      <g className="trail" style={{ fill }}>
        {Array.from({ length: TRAIL }, (_, i) => (
          <circle key={i} ref={(n) => {
            tail.current[i] = n;
            if (n && !n.hasAttribute("cx")) { n.setAttribute("cx", String(at[0])); n.setAttribute("cy", String(at[1])); }
          }} r={1.35 * (1 - i / TRAIL)} style={{ opacity: 0.45 * (1 - i / TRAIL) }} />
        ))}
      </g>
      <g ref={g} className="ball">
        <circle r="3.4" className="halo" style={{ fill }} />
        <circle r="1.5" className="core" />
      </g>
    </>
  );
}

/** A pass as a tapered ribbon: wide where it was played, a point where it arrived, so direction reads at a glance. */
function taperedPass(p: Touch): string {
  const { c } = passCurve(p);
  const x1 = p.x ?? 0, y1 = p.y ?? 0, x2 = p.ex ?? x1, y2 = p.ey ?? y1;
  const at = (u: number): [number, number] => {
    const a = 1 - u;
    return [a * a * x1 + 2 * a * u * c[0] + u * u * x2, a * a * y1 + 2 * a * u * c[1] + u * u * y2];
  };
  const n = 12, w0 = 0.55, left: string[] = [], right: string[] = [];
  for (let i = 0; i <= n; i++) {
    const u = i / n, [x, y] = at(u), [xa, ya] = at(Math.max(0, u - 0.01)), [xb, yb] = at(Math.min(1, u + 0.01));
    const len = Math.hypot(xb - xa, yb - ya) || 1, nx = -(yb - ya) / len, ny = (xb - xa) / len, w = w0 * (1 - u) + 0.08;
    left.push(`${(x + nx * w).toFixed(2)} ${(y + ny * w).toFixed(2)}`);
    right.unshift(`${(x - nx * w).toFixed(2)} ${(y - ny * w).toFixed(2)}`);
  }
  return `M${left.join("L")}L${right.join("L")}Z`;
}

/** How a goal or big chance was built: its passes numbered in order, the run with the ball between them, and the
 * shot. Drawn in the attacking side's color over everything else. */
function Chain({ shot, still = false }: { shot: Touch; still?: boolean }) {
  const passes = (shot.chain?.passes ?? []).map(([x, y, ex, ey, p], i) => ({ s: shot.s * 100 + i, t: "pass", k: shot.k, m: shot.m, p, x, y, ex, ey, o: true, pos: shot.k } as Touch));
  const start = shot.chain?.start;
  const end = shot.g ? [shot.k === 0 ? W - 0.6 : 0.6, Math.min(Math.max(shot.y ?? H / 2, 31.5), 36.5)] : [shot.k === 0 ? W : 0, H / 2];
  return (
    <g className={`chain${still ? " still" : ""}`} style={{ ["--team" as string]: TEAM[shot.k] }} aria-hidden="true">
      {start && passes[0] && Math.hypot((passes[0].x ?? 0) - start.x, (passes[0].y ?? 0) - start.y) > 3 && (
        <line x1={start.x} y1={start.y} x2={passes[0].x} y2={passes[0].y} className="carry" />
      )}
      {passes.map((p, i) => {
        const next = passes[i + 1] ?? shot;
        const gap = next.x !== undefined && Math.hypot((next.x ?? 0) - (p.ex ?? 0), (next.y ?? 0) - (p.ey ?? 0)) > 3;
        const [nx, ny] = numberAt(p, i);
        return (
          <g key={p.s} style={{ animationDelay: still ? "0s" : `${i * 0.45}s` }} className="link">
            <path d={taperedPass(p)} className="pass" />
            {gap && <line x1={p.ex} y1={p.ey} x2={next.x} y2={next.y} className="carry" />}
            <circle cx={nx} cy={ny} r="2.1" className="num-bg" />
            <text x={nx} y={ny + 1} textAnchor="middle" className="num">{i + 1}</text>
          </g>
        );
      })}
      <g className="link" style={{ animationDelay: still ? "0s" : `${passes.length * 0.45}s` }}>
        <line x1={shot.x} y1={shot.y} x2={end[0]} y2={end[1]} className="shotline" />
        <circle cx={shot.x} cy={shot.y} r="1.6" className="shooter" />
      </g>
    </g>
  );
}

/** Where a pass's number sits: beside the middle of its curve, alternating sides so neighbors don't stack. */
function numberAt(p: Touch, i: number): [number, number] {
  const { c } = passCurve(p);
  const x1 = p.x ?? 0, y1 = p.y ?? 0, x2 = p.ex ?? x1, y2 = p.ey ?? y1;
  const mx = 0.25 * x1 + 0.5 * c[0] + 0.25 * x2, my = 0.25 * y1 + 0.5 * c[1] + 0.25 * y2;
  const len = Math.hypot(x2 - x1, y2 - y1) || 1;
  const side = i % 2 ? -1 : 1;
  const x = mx - ((y2 - y1) / len) * 3 * side, y = my + ((x2 - x1) / len) * 3 * side;
  return [Math.min(W - 2, Math.max(2, x)), Math.min(H - 2, Math.max(2, y))];
}

/** "How it was built: won back by Quarani · Thornton → Fenane → Belwell" */
function builtText(shot: Touch, lang: Lang): string {
  const c = shot.chain;
  if (!c) return "";
  const names = [...c.passes.map((p) => p[4]), shot.p].map((n) => n.split(" ").slice(-1)[0])
    .filter((n, i, a) => i === 0 || n !== a[i - 1]);
  const from = c.start
    ? c.start.t === "corner" ? t("chainCorner", lang)
      : c.start.t === "kickoff" ? t("chainKickoff", lang)
        : t("chainWon", lang).replace("{p}", c.start.p.split(" ").slice(-1)[0])
    : "";
  const count = c.passes.length === 1 ? t("chainOne", lang) : t("chainN", lang).replace("{n}", String(c.passes.length));
  return `${t("chainTitle", lang)}: ${[from, count].filter(Boolean).join(", ")} · ${names.join(" → ")}`;
}

function ShotDot({ s, now = false, picked = false }: { s: Touch; now?: boolean; picked?: boolean }) {
  const r = 1.1 + (s.xg ?? 0) * 4.5;
  return (
    <>
      {picked && <circle cx={s.x} cy={s.y} r={r + 1.6} className="shot-ring" />}
      <circle cx={s.x} cy={s.y} r={r}
        className={`shot${s.g ? " goal" : s.on ? " on" : " off"}${now ? " now" : ""}`}
        style={{ ["--team" as string]: TEAM[s.k] }} />
    </>
  );
}

function writePref(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* not saved; fine for this visit */
  }
}

/** The passes of the move in progress: the latest run of passes by one team, back to the last interruption. */
function currentMove(shown: Touch[]): Touch[] {
  const out: Touch[] = [];
  let i = shown.length - 1;
  const tail = shown[i];
  const team = tail?.k;
  if (tail && tail.t === "shot") i--; // keep the build-up to a shot on screen
  for (; i >= 0 && out.length < 5; i--) {
    const x = shown[i];
    if (x.t !== "pass" || x.ex === undefined) break;
    if (x.k !== (out[0]?.k ?? (tail?.t === "shot" ? team : x.k))) break;
    out.unshift(x);
    if (!x.o) break;
  }
  return out;
}

function ballAt(x?: Touch): [number, number] | null {
  if (!x) return [W / 2, H / 2];
  if (x.t === "pass" && x.ex !== undefined && x.ey !== undefined) return [x.ex, x.ey];
  if (x.x !== undefined && x.y !== undefined) {
    if (x.t === "shot" && x.g) return [x.k === 0 ? W - 0.6 : 0.6, Math.min(Math.max(x.y, 31.5), 36.5)];
    return [x.x, x.y];
  }
  return null;
}

function describe(x: Touch, snap: MatchSnapshot, lang: Lang): string {
  const team = (x.k === 0 ? snap.home : snap.away).short;
  switch (x.t) {
    case "pass":
      return x.o ? (x.r ? `${x.p} → ${x.r}` : x.p) : `${t("tMiss", lang)} · ${x.p}`;
    case "shot":
      return x.g
        ? `${t("tGoal", lang)}! ${x.p} · ${x.xg?.toFixed(2)} xG`
        : `${t("tShot", lang)} · ${x.p} · ${x.xg?.toFixed(2)} xG · ${x.on ? t("tSaved", lang) : t("tOff", lang)}`;
    case "tackle":
      return `${t("tTackle", lang)} · ${x.p}`;
    case "interception":
      return `${t("tInterception", lang)} · ${x.p}`;
    case "save":
      return `${t("tSave", lang)} · ${x.p}`;
    case "corner":
      return `${t("tCorner", lang)} · ${team}`;
    case "foul":
      return `${t("tFoul", lang)} · ${x.p}`;
    case "yellow_card":
      return `${t("tYellow", lang)} · ${x.p}`;
    case "red_card":
      return `${t("tRed", lang)} · ${x.p}`;
    case "substitution":
      return `${t("tSub", lang)} · ${team}`;
    default:
      return `${t("tKickoff", lang)} · ${team}`;
  }
}

function Marker({ m, age }: { m: Touch; age: number }) {
  const style = { stroke: TEAM[m.k], opacity: Math.max(0.25, 1 - age * 0.15) };
  const { x = 0, y = 0 } = m;
  switch (m.t) {
    case "tackle":
      return <path className="mk" d={`M${x - 1.6} ${y - 1.6}L${x + 1.6} ${y + 1.6}M${x + 1.6} ${y - 1.6}L${x - 1.6} ${y + 1.6}`} style={style} />;
    case "interception":
      return <path className="mk" d={`M${x} ${y - 1.9}L${x + 1.9} ${y}L${x} ${y + 1.9}L${x - 1.9} ${y}Z`} style={style} />;
    case "save":
      return <rect className="mk" x={x - 1.4} y={y - 3.2} width="2.8" height="6.4" rx="1" style={style} />;
    case "corner":
      return <path className="mk" d={`M${x} ${y}V${y - 4.5}L${x + 3} ${y - 3.4}L${x} ${y - 2.3}`} style={style} />;
    default: // foul
      return <circle className="mk" cx={x} cy={y} r="1.3" style={{ ...style, strokeDasharray: "0.8 0.6" }} />;
  }
}

function PitchMarkings() {
  const stripes = Array.from({ length: 7 }, (_, i) => i);
  return (
    <g className="markings">
      <rect x="0" y="0" width={W} height={H} className="turf" />
      {stripes.map((i) => (i % 2 ? <rect key={i} x={i * 15} y="0" width="15" height={H} className="stripe" /> : null))}
      <rect x="0" y="0" width={W} height={H} className="line" />
      <line x1={W / 2} y1="0" x2={W / 2} y2={H} className="line" />
      <circle cx={W / 2} cy={H / 2} r="9.15" className="line" />
      <circle cx={W / 2} cy={H / 2} r="0.45" className="spot" />
      {[0, 1].map((side) => {
        const dir = side === 0 ? 1 : -1;
        const gx = side === 0 ? 0 : W;
        return (
          <g key={side}>
            <rect x={side === 0 ? 0 : W - 16.5} y="13.84" width="16.5" height="40.32" className="line" />
            <rect x={side === 0 ? 0 : W - 5.5} y="24.84" width="5.5" height="18.32" className="line" />
            <circle cx={gx + dir * 11} cy={H / 2} r="0.45" className="spot" />
            <path d={`M${gx + dir * 16.5} ${H / 2 - 7.3}A9.15 9.15 0 0 ${side === 0 ? 1 : 0} ${gx + dir * 16.5} ${H / 2 + 7.3}`} className="line" />
            <rect x={side === 0 ? -2 : W} y="30.34" width="2" height="7.32" className="goalbox" />
          </g>
        );
      })}
    </g>
  );
}
