import { useEffect, useRef } from "react";
import { api } from "../api";
import { loc, t } from "../i18n";
import { useStore } from "../store";
import type { Lang, MatchSnapshot, Moment } from "../types";
import { Sparkle } from "./Icons";

export function WhyItMoved({ snap, moment, lang }: { snap: MatchSnapshot; moment: Moment; lang: Lang }) {
  const user = useStore((s) => s.user);
  const counted = useRef<string | null>(null);
  const max = Math.max(1, ...moment.drivers.map((d) => Math.abs(d.delta)));
  const side = user?.club_id === snap.home.club_id ? "home" : user?.club_id === snap.away.club_id ? "away" : null;
  const clubLine = side ? loc(moment.club_lines?.[side], lang) : "";

  useEffect(() => {
    // Reading a fresh story counts toward today's mission (once per moment, after a few seconds).
    if (!user || counted.current === moment.moment_id || moment.trigger === "kickoff") return;
    const id = moment.moment_id;
    const tm = setTimeout(() => {
      counted.current = id;
      api.activity(user.id, "read_story").then((r) => r.user && useStore.getState().setUser(r.user)).catch(() => undefined);
    }, 4000);
    return () => clearTimeout(tm);
  }, [moment.moment_id, moment.trigger, user]);

  return (
    <section className="card why" aria-live="polite">
      <div className="row">
        <span className="eyebrow gold">{t("whyMoved", lang)} · {moment.minute}'</span>
        {moment.source === "agents" ? (
          <span className="chip agents" title={(moment.agent_trace ?? []).map((a) => `${a.agent} ${a.ms}ms`).join(", ")}>
            <Sparkle /> {t("agents", lang)}
          </span>
        ) : (
          <span className="chip ghost">{t("gaffer", lang)}</span>
        )}
      </div>
      <h3>{loc(moment.headline, lang)}</h3>
      <p>{loc(moment.story, lang)}</p>
      {moment.drivers.length > 0 && (
        <div className="drivers">
          {moment.drivers.slice(0, 4).map((d) => (
            <div className="driver" key={d.component}>
              <span>{loc(d.label, lang)}</span>
              <span className="d">{d.delta > 0 ? "+" : ""}{d.delta}</span>
              <div className="bar">
                <span className={d.delta < 0 ? "neg" : undefined} style={{ width: `${(Math.abs(d.delta) / max) * 100}%` }} />
              </div>
            </div>
          ))}
        </div>
      )}
      {clubLine && <div className="clubline">{clubLine}</div>}
      {user?.persona === "analyst" && loc(moment.analyst, lang) && <div className="analyst">{loc(moment.analyst, lang)}</div>}
    </section>
  );
}
