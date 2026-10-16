import { useEffect, useState } from "react";
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
import { Feed, StatsPanel } from "../components/Panels";
import { WhyItMoved } from "../components/WhyItMoved";
import { t } from "../i18n";
import { useStore } from "../store";
import type { Booking, Lang, MatchSummary } from "../types";

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
  const user = useStore((s) => s.user);
  const connected = useStore((s) => s.connected);

  useEffect(() => {
    watch(id).catch(() => undefined);
    return () => unwatch(id);
  }, [id, connected, watch, unwatch]);

  const [moments, setMoments] = useState(false);
  const wide = useWide();
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
  const analyst = user?.persona === "analyst";
  const head = (
    <>
      {snap.private && (
        <div className="replay-bar" role="note">
          <span>{t("bmPrivate", lang)}</span>
          <a href="#/">{t("bmBackLive", lang)}</a>
        </div>
      )}
      <section className="card">
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
  const why = moment && <WhyItMoved snap={snap} moment={moment} lang={lang} />;
  const touch = <Touchline snap={snap} lang={lang} />;
  const call = <CallIt snap={snap} lang={lang} />;
  const ask = <AskGaffer snap={snap} lang={lang} />;
  const motm = <PlayerOfMatch snap={snap} lang={lang} />;
  const season = <SeasonOutlook snap={snap} lang={lang} />;
  const story = <MatchStory snap={snap} lang={lang} />;
  const stats = <StatsPanel snap={snap} lang={lang} />;
  const feed = <Feed snap={snap} lang={lang} />;

  // Now at the top, play-along in the middle, context and reference below. At full time the payoff
  // (the result, the Player of the Match, what it did to the season) moves up.
  if (wide) {
    // Two columns: the match on the left, playing along on the right.
    return (
      <div className="page match-wide">
        <div className="match-cols">
          <div className="col">
            {head}
            {why}
            {story}
            {feed}
          </div>
          <div className="col">
            {finished ? <>{motm}{season}{touch}{ask}{call}</> : <>{touch}{call}{ask}{motm}{season}</>}
            {stats}
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="page">
      {head}
      {why}
      {finished ? <>{motm}{season}{story}{ask}{touch}{call}</> : <>{touch}{call}{ask}{motm}{season}{story}</>}
      {analyst && stats}
      {feed}
      {!analyst && stats}
    </div>
  );
}

/** Bookings under a team, like a broadcast scoreboard: each card with the player and minute. */
function Bookings({ cards, reds, lang }: { cards: Booking[]; reds: number; lang: Lang }) {
  if (!cards.length && !reds) return null;
  const shown = cards.slice(-3);
  return (
    <div className="bookings">
      {shown.map((c, i) => (
        <span key={i} className={`bk ${c.c === "r" ? "red" : "yellow"}`} title={t(c.c === "r" ? "tRed" : "tYellow", lang)}>
          <i />
          {c.p} {c.m}'
        </span>
      ))}
      {cards.length > shown.length && <span className="bk more">+{cards.length - shown.length}</span>}
      {reds > 0 && <span className="men" title={t("redCards", lang)}>{t("menLeft", lang).replace("{n}", String(11 - reds))}</span>}
    </div>
  );
}
