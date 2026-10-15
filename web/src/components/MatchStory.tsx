import { useState } from "react";
import { loc, t } from "../i18n";
import type { Key } from "../i18n";
import type { Lang, MatchSnapshot, Moment } from "../types";
import { Sparkle } from "./Icons";
import { Listen, storyText } from "./Listen";
import { UnderTheHood } from "./UnderTheHood";

const LABEL: Record<string, Key> = {
  kickoff: "tKickoff", goal: "goalWord", red_card: "tRed", half_time: "halfTime", full_time: "fullTime",
  swing: "trSwing", swing_draw: "trSwing", pulse: "trPulse",
};
const TEAM = ["var(--home)", "var(--away)"];
const order = (m: Moment) => Number(m.moment_id.split("-m").pop()) || 0;

/** Match story: every story published in this match, newest first, so nothing said is lost. */
export function MatchStory({ snap, lang }: { snap: MatchSnapshot; lang: Lang }) {
  const [all, setAll] = useState(false);
  const [hood, setHood] = useState<Moment | null>(null);
  const list = [...snap.moments].sort((a, b) => order(b) - order(a));
  const shown = all ? list : list.slice(0, 4);

  return (
    <section className="card story" aria-label={t("storyTitle", lang)}>
      <div className="row">
        <span className="eyebrow gold">{t("storyTitle", lang)}</span>
        {list.length > 4 && (
          <button className="linkbtn" onClick={() => setAll(!all)} aria-expanded={all}>
            {all ? t("showLess", lang) : `${t("showAll", lang)} (${list.length})`}
          </button>
        )}
      </div>
      {list.length === 0 ? (
        <p className="muted" style={{ fontSize: 13, margin: "8px 0 0" }}>{t("storyEmpty", lang)}</p>
      ) : (
        <ol className="st">
          {shown.map((m) => {
            const side = m.focus === 0 ? "home" : "away";
            const club = m.focus === 0 ? snap.home : snap.away;
            const before = Math.round(m.before[side] * 100);
            const after = Math.round(m.after[side] * 100);
            return (
              <li key={m.moment_id} className={`st-item ${m.trigger}`}>
                <span className="st-min">{m.minute}'</span>
                <div className="st-body">
                  <div className="st-top">
                    <span className="st-tag">{t(LABEL[m.trigger] ?? "trPulse", lang)}</span>
                    <span className="st-score">{m.score[0]}-{m.score[1]}</span>
                    <Listen kind="story" id={m.moment_id} matchId={snap.match_id} lang={lang} compact
                      text={storyText(loc(m.headline, lang), loc(m.story, lang))} />
                    {m.source === "agents" && m.agent_trace?.length ? (
                      <button className="st-ai" onClick={() => setHood(m)} aria-label={t("uth", lang)}><Sparkle size={11} /> {t("agents", lang)}</button>
                    ) : null}
                  </div>
                  <b>{loc(m.headline, lang)}</b>
                  <p>{loc(m.story, lang)}</p>
                  {m.trigger !== "kickoff" && before !== after && (
                    <span className="st-chance">
                      <i style={{ background: TEAM[m.focus] }} />
                      {club.short} {before}% <span className={after < before ? "down" : "up"}>→ {after}%</span>
                    </span>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
      {hood?.agent_trace && <UnderTheHood kind="story" trace={hood.agent_trace} latencyMs={hood.latency_ms} onClose={() => setHood(null)} />}
    </section>
  );
}
