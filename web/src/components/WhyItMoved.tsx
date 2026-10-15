import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { loc, t } from "../i18n";
import { useStore } from "../store";
import type { Lang, MatchSnapshot, Moment, User } from "../types";
import { Sparkle } from "./Icons";
import { Listen, storyText } from "./Listen";
import { UnderTheHood } from "./UnderTheHood";

export function WhyItMoved({ snap, moment, lang }: { snap: MatchSnapshot; moment: Moment; lang: Lang }) {
  const user = useStore((s) => s.user);
  const counted = useRef<string | null>(null);
  const [hood, setHood] = useState(false);
  const max = Math.max(1, ...moment.drivers.map((d) => Math.abs(d.delta)));
  const side = user?.club_id === snap.home.club_id ? "home" : user?.club_id === snap.away.club_id ? "away" : null;
  const clubLine = side ? loc(moment.club_lines?.[side], lang) : "";

  useEffect(() => {
    // Reading a fresh story counts toward today's mission (once per moment, after a few seconds).
    if (!user || counted.current === moment.moment_id || moment.trigger === "kickoff") return;
    const id = moment.moment_id;
    const tm = setTimeout(() => {
      counted.current = id;
      const done = (r: { user: User | null }) => r.user && useStore.getState().setUser(r.user);
      api.activity(user.id, "read_story", lang).then(done).catch(() => undefined);
      if (moment.trigger === "half_time") api.activity(user.id, "halftime").then(done).catch(() => undefined);
    }, 4000);
    return () => clearTimeout(tm);
  }, [moment.moment_id, moment.trigger, user]); // eslint-disable-line react-hooks/exhaustive-deps

  const analyst = user?.persona === "analyst";
  // Fans get the two biggest reasons in words; analysts get every driver with its points.
  const drivers = analyst ? moment.drivers.slice(0, 4) : [...moment.drivers].sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta)).slice(0, 2);

  return (
    <section className="card why" aria-live="polite">
      <div className="row">
        <span className="eyebrow gold">{t("whyMoved", lang)} · {moment.minute}'</span>
        {moment.source === "agents" ? (
          <button className="chip agents" onClick={() => setHood(true)} aria-label={t("uth", lang)}>
            <Sparkle /> {t("agents", lang)} <span className="chev">›</span>
          </button>
        ) : (
          <span className="chip ghost">{t("gaffer", lang)}</span>
        )}
      </div>
      <h3>{loc(moment.headline, lang)}</h3>
      <p>{loc(moment.story, lang)}</p>
      <div className="why-actions">
        <Listen kind="story" id={moment.moment_id} matchId={snap.match_id} lang={lang}
          text={storyText(loc(moment.headline, lang), loc(moment.story, lang))} />
      </div>
      {drivers.length > 0 && (
        <div className={`drivers${analyst ? "" : " plain"}`}>
          {drivers.map((d) => (
            <div className="driver" key={d.component}>
              <span>{loc(d.label, lang)}</span>
              {analyst ? (
                <span className="d">{d.delta > 0 ? "+" : ""}{d.delta}</span>
              ) : (
                <span className={`arrow${d.delta < 0 ? " neg" : ""}`} aria-label={d.delta < 0 ? "lowered it" : "raised it"}>{d.delta < 0 ? "↓" : "↑"}</span>
              )}
              <div className="bar">
                <span className={d.delta < 0 ? "neg" : undefined} style={{ width: `${(Math.abs(d.delta) / max) * 100}%` }} />
              </div>
            </div>
          ))}
        </div>
      )}
      {clubLine && (
        <div className="clubline">
          {moment.trigger === "half_time" && <span className="talk">{t("teamTalk", lang)}</span>}
          {clubLine}
        </div>
      )}
      {analyst && loc(moment.analyst, lang) && <div className="analyst">{loc(moment.analyst, lang)}</div>}
      {hood && moment.agent_trace?.length ? (
        <UnderTheHood kind="story" trace={moment.agent_trace} latencyMs={moment.latency_ms} onClose={() => setHood(false)} />
      ) : null}
    </section>
  );
}
