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
          <svg className="pitch" viewBox={`-3 -3 ${W + 6} ${H + 6}`} role="img"
            aria-label={view === "live" ? (last ? describe(last, snap, lang) : t("touchline", lang)) : t("vShots", lang)}>
            <PitchMarkings />
            {view === "live" && (
              <>
                {recentShot && <ShotDot s={recentShot} now={recentShot.s === last?.s} />}
                {markers.map((m, i) => (
                  <Marker key={`m-${m.s}`} m={m} age={markers.length - 1 - i} />
                ))}
                {passes.map((p, i) => (
                  <path key={`p-${p.s}`} d={passCurve(p).d}
                    className={`pass${p.o ? "" : " cut"}`}
                    style={{ stroke: TEAM[p.k], opacity: 0.25 + 0.75 * ((i + 1) / passes.length) }} />
                ))}
                {ball && <Ball last={last} at={ball} fill={TEAM[possession ?? last?.k ?? 0]} />}
              </>
            )}
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
            <div className="pitch-foot">
              <span className="dir"><Crest club={snap.home} size="sm" />{snap.home.short} <b>→</b></span>
              <span className="ticker" aria-live="polite">
                {possession !== null && snap.status !== "scheduled" && <i className="possdot" style={{ background: TEAM[possession] }} />}
                {last ? `${last.m}'  ${describe(last, snap, lang)}` : ""}
              </span>
              <span className="dir right"><b>←</b> {snap.away.short}<Crest club={snap.away} size="sm" /></span>
            </div>
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
 * A pass drawn as a gentle arc, the way a ball curls or is lofted, rather than a ruler line.
 * The bend grows with distance, and its side is fixed per pass (so it never flickers) and
 * flipped when it would leave the pitch.
 */
function passCurve(p: Touch): { c: [number, number]; d: string } {
  const x1 = p.x ?? 0, y1 = p.y ?? 0, x2 = p.ex ?? x1, y2 = p.ey ?? y1;
  const dx = x2 - x1, dy = y2 - y1;
  const len = Math.hypot(dx, dy) || 1;
  const bend = Math.min(8, len * 0.17);
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

/** The ball. After a pass it travels along the same arc as the line, slowing as it arrives. */
function Ball({ last, at, fill }: { last?: Touch; at: [number, number]; fill: string }) {
  const g = useRef<SVGGElement>(null);
  const pos = useRef<[number, number] | null>(null);
  useEffect(() => {
    const el = g.current;
    if (!el) return;
    const put = (q: [number, number]) => {
      pos.current = q;
      el.setAttribute("transform", `translate(${q[0].toFixed(2)} ${q[1].toFixed(2)})`);
    };
    const from = pos.current;
    if (!from || reduceMotion || (from[0] === at[0] && from[1] === at[1])) {
      put(at);
      return;
    }
    const c = last?.t === "pass" && last.ex !== undefined ? passCurve(last).c : null;
    const t0 = performance.now();
    const dur = c ? 300 : 240;
    let raf = 0;
    const step = (now: number) => {
      const u = Math.min(1, (now - t0) / dur);
      const e = 1 - (1 - u) * (1 - u);
      const a = 1 - e;
      put(c
        ? [a * a * from[0] + 2 * a * e * c[0] + e * e * at[0], a * a * from[1] + 2 * a * e * c[1] + e * e * at[1]]
        : [from[0] + (at[0] - from[0]) * e, from[1] + (at[1] - from[1]) * e]);
      if (u < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [at[0], at[1], last?.s]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <g ref={g} className="ball">
      <circle r="3.4" className="halo" style={{ fill }} />
      <circle r="1.5" className="core" />
    </g>
  );
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
