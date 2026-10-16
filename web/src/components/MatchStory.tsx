import { useState } from "react";
import { loc, t } from "../i18n";
import type { Key } from "../i18n";
import type { FeedItem, Lang, MatchSnapshot, Moment } from "../types";
import { feedText } from "../words";
import { EventIcon, kindOf } from "./EventIcon";
import { Sparkle } from "./Icons";
import { Listen, storyText } from "./Listen";
import { UnderTheHood } from "./UnderTheHood";

const LABEL: Record<string, Key> = {
  kickoff: "tKickoff", goal: "goalWord", red_card: "tRed", half_time: "halfTime", full_time: "fullTime",
  swing: "trSwing", swing_draw: "trSwing", pulse: "trPulse", var_overturned: "trVar",
};
const TEAM = ["var(--home)", "var(--away)"];
const order = (m: Moment) => Number(m.moment_id.split("-m").pop()) || 0;
// Feed events a story already tells (the same thing at the same minute), so "All events" doesn't repeat them.
const TOLD_BY: Record<string, string> = { goal: "goal", red_card: "red_card", half_time: "half_time",
  full_time: "full_time", var_decision: "var_overturned" };

type Row = { kind: "story"; minute: number; rank: number; m: Moment } | { kind: "event"; minute: number; rank: number; f: FeedItem };

/** The match timeline: every story the Gaffer told (Key moments), or those plus every chance, card,
 * substitution and VAR check in between (All events). Newest first. */
export function MatchStory({ snap, lang }: { snap: MatchSnapshot; lang: Lang }) {
  const [all, setAll] = useState(false);
  const [every, setEvery] = useState(false);
  const [hood, setHood] = useState<Moment | null>(null);
  const stories: Row[] = snap.moments.map((m) => ({ kind: "story", minute: m.minute, rank: 1e6 + order(m), m }));
  const told = (f: FeedItem) => {
    const trig = TOLD_BY[f.type];
    if (!trig || (f.type === "var_decision" && f.decision !== "ruled_out")) return false;
    return snap.moments.some((m) => m.trigger === trig && Math.abs(m.minute - f.minute) <= 1);
  };
  const events: Row[] = every ? snap.feed.filter((f) => !told(f)).map((f) => ({ kind: "event", minute: f.minute, rank: f.seq, f })) : [];
  const list = [...stories, ...events].sort((a, b) => b.minute - a.minute || b.rank - a.rank);
  const limit = every ? 8 : 4;
  const shown = all ? list : list.slice(0, limit);

  return (
    <section className="card story" aria-label={t("storyTitle", lang)}>
      <div className="row">
        <span className="eyebrow gold">{t("storyTitle", lang)}</span>
        <div className="seg mini tl-mode" role="group" aria-label={t("storyTitle", lang)}>
          <button className={`tab${!every ? " sel" : ""}`} aria-pressed={!every} onClick={() => setEvery(false)}>{t("tlKey", lang)}</button>
          <button className={`tab${every ? " sel" : ""}`} aria-pressed={every} onClick={() => setEvery(true)}>{t("tlAll", lang)}</button>
        </div>
      </div>
      {list.length === 0 ? (
        <p className="muted" style={{ fontSize: 13, margin: "8px 0 0" }}>{t("storyEmpty", lang)}</p>
      ) : (
        <ol className="st">
          {shown.map((r) => r.kind === "event" ? (
            <li key={`e${r.f.seq}`} className={`st-ev ${r.f.type}`}>
              <span className="st-min">{r.f.minute}'</span>
              <EventIcon kind={kindOf(r.f.type)} size={16} />
              <span className="st-ev-text">{feedText(r.f, snap, lang)}</span>
            </li>
          ) : (
            <StoryItem key={r.m.moment_id} m={r.m} snap={snap} lang={lang} onHood={setHood} />
          ))}
        </ol>
      )}
      {list.length > limit && (
        <button className="linkbtn st-more" onClick={() => setAll(!all)} aria-expanded={all}>
          {all ? t("showLess", lang) : `${t("showAll", lang)} (${list.length})`}
        </button>
      )}
      {hood?.agent_trace && <UnderTheHood kind="story" trace={hood.agent_trace} latencyMs={hood.latency_ms} onClose={() => setHood(null)} />}
    </section>
  );
}

function StoryItem({ m, snap, lang, onHood }: { m: Moment; snap: MatchSnapshot; lang: Lang; onHood: (m: Moment) => void }) {
  const side = m.focus === 0 ? "home" : "away";
  const club = m.focus === 0 ? snap.home : snap.away;
  const before = Math.round(m.before[side] * 100);
  const after = Math.round(m.after[side] * 100);
  return (
    <li className={`st-item ${m.trigger}`}>
      <span className="st-min">{m.minute}'</span>
      <div className="st-body">
        <div className="st-top">
          <span className="st-tag"><EventIcon kind={kindOf(m.trigger)} size={15} />{t(LABEL[m.trigger] ?? "trPulse", lang)}</span>
          <span className="st-score">{m.score[0]}-{m.score[1]}</span>
          <Listen kind="story" id={m.moment_id} matchId={snap.match_id} lang={lang} compact
            text={storyText(loc(m.headline, lang), loc(m.story, lang))} />
          {m.source === "agents" && m.agent_trace?.length ? (
            <button className="st-ai" onClick={() => onHood(m)} aria-label={t("uth", lang)}><Sparkle size={11} /> {t("agents", lang)}</button>
          ) : null}
        </div>
        <b>{loc(m.headline, lang)}</b>
        <p>{loc(m.story, lang)}</p>
        {m.trigger !== "kickoff" && m.trigger !== "full_time" && before !== after && (
          <span className="st-chance">
            <i style={{ background: TEAM[m.focus] }} />
            {club.short} {before}% <span className={after < before ? "down" : "up"}>→ {after}%</span>
          </span>
        )}
      </div>
    </li>
  );
}
