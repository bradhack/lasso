import type React from "react";
import { useEffect, useRef, useState } from "react";
import { AskGaffer } from "../components/AskGaffer";
import { Crest, pct } from "../components/bits";
import { CallIt } from "../components/CallIt";
import { Back, Chevron } from "../components/Icons";
import { Believe } from "../components/Believe";
import { Touchline } from "../components/Touchline";
import { VarCheck } from "../components/VarCheck";
import { RACE_LABEL, SeasonOutlook } from "../components/SeasonOutlook";
import { PlayerOfMatch } from "../components/PlayerOfMatch";
import { BigMomentsCard, BigMomentsSheet } from "../components/BigMoments";
import { MatchStory } from "../components/MatchStory";
import { Meter } from "../components/Meter";
import { StatsPanel } from "../components/Panels";
import { MatchBanner } from "../components/MatchBanner";
import { WhyItMoved } from "../components/WhyItMoved";
import { stopListening } from "../components/Listen";
import { t } from "../i18n";
import { useStore } from "../store";
import type { Key } from "../i18n";
import type { Booking, Lang, MatchSnapshot, MatchSummary } from "../types";

function statusLabel(m: MatchSummary, lang: Lang) {
  if (m.status === "finished") return t("fullTime", lang);
  if (m.status === "half_time") return t("halfTime", lang);
  if (m.status === "scheduled") return t("upNext", lang);
  return `${m.minute}'`;
}

const SHOWCASE = "S5-MD07-03";
const WIDE = "(min-width: 960px)";

/** True on screens wide enough for two columns (desktop and landscape tablets). */
export function useWide() {
  const [wide, setWide] = useState(() => typeof window !== "undefined" && !!window.matchMedia?.(WIDE).matches);
  useEffect(() => {
    const m = window.matchMedia?.(WIDE);
    if (!m) return;
    const on = () => setWide(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  return wide;
}

export function Lobby() {
  const matches = useStore((s) => s.matches);
  const lang = useStore((s) => s.lang);
  const live = matches.filter((m) => m.status === "live" || m.status === "half_time");
  const other = matches.filter((m) => !(m.status === "live" || m.status === "half_time"));
  return (
    <div className="page lobby">
      <div className="hero">
        <span className="eyebrow gold">{t("liveNow", lang)}</span>
        <h1>{t("heroA", lang)} <em>{t("heroB", lang)}</em></h1>
        <p>{t("heroSub", lang)}</p>
      </div>
      {matches.length > 0 && <BigMomentsCard matchId={(matches.find((m) => m.match_id === SHOWCASE) ?? matches[0]).match_id} lang={lang} />}
      {[...live, ...other].map((m) => (
        <a key={m.match_id} className="card matchcard" href={`#/match/${m.match_id}`}>
          <div className="row">
            <span className="eyebrow">{t("league", lang)} · {t("mdShort", lang).replace("{n}", String(Number(m.match_id.split("-MD")[1]?.slice(0, 2))))}</span>
            <span style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 700, fontSize: 13 }}>
              {(m.status === "live") && <i className="dot pulse" />}
              {statusLabel(m, lang)}
            </span>
          </div>
          <div className="teams">
            <span style={{ display: "flex", alignItems: "center", gap: 10 }}><Crest club={m.home} size="sm" />{m.home.name}</span>
            <span className="g">{m.score[0]}</span>
            <span style={{ display: "flex", alignItems: "center", gap: 10 }}><Crest club={m.away} size="sm" round />{m.away.name}</span>
            <span className="g">{m.score[1]}</span>
          </div>
          <div className="row winline">
            <span className="eyebrow">{t("meter", lang)}</span>
            <span className="callit-link">
              {t("callIt", lang)} <Chevron size={14} />
            </span>
          </div>
          <div className="meter-bar" style={{ height: 8, marginTop: 6 }}>
            <div className="h" style={{ width: `${m.probs.home * 100}%` }} />
            <div className="d" style={{ width: `${m.probs.draw * 100}%` }} />
            <div className="a" style={{ width: `${m.probs.away * 100}%` }} />
          </div>
          <div className="winlabels">
            <span><i className="key h" /><b>{pct(m.probs.home)}</b> {m.home.short}</span>
            <span><i className="key d" /><b>{pct(m.probs.draw)}</b> {t("draw", lang)}</span>
            <span><i className="key a" /><b>{pct(m.probs.away)}</b> {m.away.short}</span>
          </div>
          {m.race && m.race !== "none" && <span className="race-tag">{t(RACE_LABEL[m.race], lang)}</span>}
        </a>
      ))}
    </div>
  );
}

export function MatchPage({ id }: { id: string }) {
  const snap = useStore((s) => s.snapshots[id]);
  const watch = useStore((s) => s.watch);
  const unwatch = useStore((s) => s.unwatch);
  const lang = useStore((s) => s.lang);
  const connected = useStore((s) => s.connected);

  useEffect(() => {
    watch(id).catch(() => undefined);
    return () => {
      unwatch(id);
      stopListening(); // leaving this match: stop reading it aloud
    };
  }, [id, connected, watch, unwatch]);

  const [moments, setMoments] = useState(false);
  const wide = useWide();
  const [tab, setTab] = useState<Tab>("live");
  const [side, setSide] = useState<Tab | null>(null);  // desktop: the right column's tab (default by phase)
  const calls = useStore((s) => s.calls);
  const pick = useStore((s) => s.motmPicks[id]);
  const scoreRef = useRef<HTMLElement>(null);
  const headRef = useRef<HTMLDivElement>(null);
  useKeepPlace(headRef, !!snap && !wide);
  const pinned = useOffscreen(scoreRef, !wide && !!snap);
  const [barH, setBarH] = useState(64);  // the top bar's height: the mini scoreboard and tabs stick below it
  useEffect(() => { setBarH(Math.round(document.querySelector(".topbar")?.getBoundingClientRect().height ?? 64)); }, [wide]);
  useEffect(() => { setTab("live"); setSide(null); }, [id]);
  const [missing, setMissing] = useState(false);
  useEffect(() => {
    setMissing(false);
    if (!id.includes("~")) return;
    const tm = window.setTimeout(() => { if (!useStore.getState().snapshots[id]) setMissing(true); }, 4000);
    return () => window.clearTimeout(tm);
  }, [id]);
  if (!snap && missing) {
    return (
      <div className="page"><div className="empty">
        <p>{t("bmEnded", lang)}</p>
        <a className="cta" href="#/" style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", textDecoration: "none" }}>{t("bmBackLive", lang)}</a>
      </div></div>
    );
  }
  if (!snap) return <div className="page"><div className="empty">…</div></div>;
  const moment = [...snap.moments].reverse().find((m) => m.trigger !== "kickoff") ?? snap.moments[snap.moments.length - 1];

  const finished = snap.status === "finished";
  const head = (
    <>
      {snap.private && (
        <div className="replay-bar" role="note">
          <span>{t("bmPrivate", lang)}</span>
          <a href="#/">{t("bmBackLive", lang)}</a>
        </div>
      )}
      <section className="card" ref={scoreRef}>
        <div className="row" style={{ fontSize: 12 }}>
          <a href="#/" aria-label={t("backLive", lang)} style={{ display: "flex", alignItems: "center", color: "var(--muted)" }}>
            <Back size={18} /> <span className="eyebrow" style={{ marginLeft: 4 }}>{t("league", lang)}</span>
          </a>
          <span style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 700 }}>
            {snap.private && <span className="pill replay">{t("bmReplay", lang)}</span>}
            {snap.status === "live" && <i className="dot pulse" />}
            {statusLabel(snap, lang)}
          </span>
        </div>
        <div className="scoreboard">
          <div className="team"><Crest club={snap.home} />{snap.home.name}<Bookings cards={(snap.cards ?? []).filter((c) => c.k === 0)} reds={snap.reds[0]} lang={lang} /></div>
          <div className="score" aria-label={`${snap.score[0]} to ${snap.score[1]}`}>{snap.score[0]}<span className="sep">:</span>{snap.score[1]}</div>
          <div className="team"><Crest club={snap.away} round />{snap.away.name}<Bookings cards={(snap.cards ?? []).filter((c) => c.k === 1)} reds={snap.reds[1]} lang={lang} /></div>
        </div>
        <Meter snap={snap} lang={lang} />
        <button className="linkbtn bm-open" onClick={() => setMoments(true)} aria-haspopup="dialog">▶ {t("bmButton", lang)}</button>
      </section>
      {moments && <BigMomentsSheet matchId={snap.source_id ?? snap.match_id} lang={lang} onClose={() => setMoments(false)} />}
      <VarCheck snap={snap} lang={lang} />
      <Believe snap={snap} lang={lang} />
    </>
  );
  // "Ask the Gaffer" from Why it moved: open the tab it's on and bring the question box into view.
  const goAsk = () => {
    if (wide) setSide("play");
    else setTab("play");
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const card = document.querySelector<HTMLElement>(".card.ask");
      card?.scrollIntoView({ behavior: reduceMotionNow() ? "auto" : "smooth", block: "start" });
      card?.classList.add("flash");
      window.setTimeout(() => card?.classList.remove("flash"), 1400);
    }));
  };
  const why = moment && <WhyItMoved snap={snap} moment={moment} lang={lang} onAsk={goAsk} />;
  const touch = <Touchline snap={snap} lang={lang} />;
  const call = <CallIt snap={snap} lang={lang} />;
  const ask = <AskGaffer snap={snap} lang={lang} />;
  const motm = <PlayerOfMatch snap={snap} lang={lang} />;
  const season = <SeasonOutlook snap={snap} lang={lang} />;
  const story = <MatchStory snap={snap} lang={lang} />;
  const stats = <StatsPanel snap={snap} lang={lang} />;
  // Play gets a dot when there's something to do: a call this fan hasn't made, or a vote they haven't cast.
  const callOpen = snap.markets.some((m) => m.status === "open" && !calls[m.market_id]);
  const dots: Partial<Record<Tab, boolean>> = { play: callOpen || (!!snap.impact?.open && !pick && !finished) };
  // Ask & play: questions first. Call it comes and goes as questions open and close, so anything under it would
  // jump while a fan is reading or typing; with Ask on top, nothing above it changes size.
  const play = finished ? <>{ask}{call}</> : <>{ask}{call}{motm}</>;
  const table = <>{season}{stats}</>;

  if (wide) {
    // Two columns: the match on the left; the pitch, then Play or Table & stats, on the right.
    const right = side ?? (finished ? "table" : "play");
    return (
      <div className="page match-wide">
        <MatchBanner snap={snap} lang={lang} />
        <div className="match-cols">
          <div className="col">
            {head}
            {why}
            {finished && motm}
            {story}
          </div>
          <div className="col">
            {touch}
            <MatchTabs tabs={["play", "table"]} value={right} onChange={setSide} dots={dots} lang={lang} idp="d" />
            <div className="tabpanel" role="tabpanel" id={`d-panel-${right}`} aria-labelledby={`d-tab-${right}`}>
              {right === "play" ? play : table}
            </div>
          </div>
        </div>
      </div>
    );
  }
  // Phones: the score and Gauge, then three tabs (Live, Play, Table & stats). At full time the payoff
  // (the result, the Player of the Match) is on Live.
  return (
    <div className="page" style={{ ["--tabs-top" as string]: `${barH + (pinned ? MINI_H + 6 : 0)}px` }}>
      <MatchBanner snap={snap} lang={lang} />
      {pinned && <MiniScore snap={snap} lang={lang} top={barH} onTop={() => scoreRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })} />}
      <div ref={headRef}>{head}</div>
      <MatchTabs tabs={["live", "play", "table"]} value={tab} onChange={setTab} dots={dots} lang={lang} idp="m" sticky />
      <div className="tabpanel" role="tabpanel" id={`m-panel-${tab}`} aria-labelledby={`m-tab-${tab}`}>
        {tab === "live" && (finished ? <>{why}{motm}{story}{touch}</> : <>{why}{touch}{story}</>)}
        {tab === "play" && play}
        {tab === "table" && table}
      </div>
    </div>
  );
}

/**
 * Keep the fan's place when the score area grows or shrinks (a card on the scoreboard, the VAR check, Touch the
 * sign). When they're reading or typing in the tabs below it, scroll by the same amount, so what they were
 * looking at stays put. The browser's own scroll anchoring is off on this page (Safari has none, and Chrome's
 * missed these), so there's one rule everywhere.
 */
function useKeepPlace(ref: React.RefObject<HTMLDivElement | null>, active: boolean) {
  useEffect(() => {
    const el = ref.current;
    if (!active || !el || typeof ResizeObserver === "undefined") return;
    document.documentElement.classList.add("keep-place");
    let h = el.getBoundingClientRect().height;
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect();
      const d = r.height - h;
      h = r.height;
      if (d === 0) return;
      const typing = !!document.activeElement?.closest(".tabpanel");
      const below = r.bottom - d < window.innerHeight * 0.45; // most of the screen was the tab, not the score
      if (typing || below) window.scrollBy(0, d);
    });
    ro.observe(el);
    return () => {
      ro.disconnect();
      document.documentElement.classList.remove("keep-place");
    };
  }, [ref, active]);
}

const reduceMotionNow = () => typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

type Tab = "live" | "play" | "table";
const TAB_LABEL: Record<Tab, Key> = { live: "tabLive", play: "tabPlay", table: "tabTable" };

/** Tabs with arrow-key movement (the ARIA tabs pattern) and a dot for "something to do here". */
function MatchTabs({ tabs, value, onChange, dots, lang, idp, sticky = false }: {
  tabs: Tab[]; value: Tab; onChange: (t: Tab) => void; dots: Partial<Record<Tab, boolean>>; lang: Lang; idp: string; sticky?: boolean;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const move = (i: number) => {
    const n = (i + tabs.length) % tabs.length;
    onChange(tabs[n]);
    refs.current[n]?.focus();
  };
  return (
    <div className={`mtabs${sticky ? " sticky" : ""}`} role="tablist" aria-label={t("tabsLabel", lang)}>
      {tabs.map((tb, i) => (
        <button key={tb} ref={(el) => { refs.current[i] = el; }} role="tab" id={`${idp}-tab-${tb}`} aria-controls={`${idp}-panel-${tb}`}
          aria-selected={value === tb} tabIndex={value === tb ? 0 : -1} className={`mtab${value === tb ? " sel" : ""}`}
          onClick={() => onChange(tb)}
          onKeyDown={(e) => {
            if (e.key === "ArrowRight") { e.preventDefault(); move(i + 1); }
            else if (e.key === "ArrowLeft") { e.preventDefault(); move(i - 1); }
            else if (e.key === "Home") { e.preventDefault(); move(0); }
            else if (e.key === "End") { e.preventDefault(); move(tabs.length - 1); }
          }}>
          {t(TAB_LABEL[tb], lang)}
          {dots[tb] && value !== tb && <i className="tab-dot" role="img" aria-label={t("tabNew", lang)} />}
        </button>
      ))}
    </div>
  );
}

/** True once the element has scrolled out of view under the top bar (for the pinned mini scoreboard). */
function useOffscreen(ref: React.RefObject<HTMLElement | null>, enabled: boolean) {
  const [off, setOff] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!enabled || !el || typeof IntersectionObserver === "undefined") { setOff(false); return; }
    const top = Math.round(document.querySelector(".topbar")?.getBoundingClientRect().height ?? 64);
    const io = new IntersectionObserver(([e]) => setOff(!e.isIntersecting && e.boundingClientRect.top < top),
      { rootMargin: `-${top}px 0px 0px 0px`, threshold: 0 });
    io.observe(el);
    return () => io.disconnect();
  }, [ref, enabled]);
  return off;
}

/** Phones: once the scoreboard scrolls away, a slim bar keeps the score, minute and Gauge in view. */
const MINI_H = 54;

function MiniScore({ snap, lang, top, onTop }: { snap: MatchSnapshot; lang: Lang; top: number; onTop: () => void }) {
  const p = snap.probs;
  return (
    <button className="mini-score" style={{ top, height: MINI_H }} onClick={onTop} aria-label={t("miniTop", lang)}>
      <span className="ms-row">
        <span className="ms-team">{snap.home.short}</span>
        <b className="ms-score">{snap.score[0]} : {snap.score[1]}</b>
        <span className="ms-team">{snap.away.short}</span>
        <span className="ms-min">{statusLabel(snap, lang)}</span>
      </span>
      <span className="meter-bar ms-bar" aria-hidden="true">
        <span className="h" style={{ width: `${p.home * 100}%` }} />
        <span className="d" style={{ width: `${p.draw * 100}%` }} />
        <span className="a" style={{ width: `${p.away * 100}%` }} />
      </span>
    </button>
  );
}

/** Bookings under a team, like a broadcast scoreboard: each card with the player and minute. */
function Bookings({ cards, reds, lang }: { cards: Booking[]; reds: number; lang: Lang }) {
  if (!cards.length && !reds) return null;
  const shown = cards.slice(-3);
  return (
    <div className="bookings">
      {/* The cards line up as a list (left-aligned); "10 men" stays centered under them. */}
      <ul className="bk-list">
        {shown.map((c, i) => (
          <li key={i} className={`bk ${c.c === "r" ? "red" : "yellow"}`} title={t(c.c === "r" ? "tRed" : "tYellow", lang)}>
            <i aria-hidden="true" />
            <span className="sr-only">{t(c.c === "r" ? "tRed" : "tYellow", lang)}: </span>{c.p} {c.m}'
          </li>
        ))}
        {cards.length > shown.length && <li className="bk more">+{cards.length - shown.length}</li>}
      </ul>
      {reds > 0 && <span className="men" title={t("redCards", lang)}>{t("menLeft", lang).replace("{n}", String(11 - reds))}</span>}
    </div>
  );
}
