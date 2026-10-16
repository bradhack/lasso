import { useEffect, useState } from "react";
import { t } from "../i18n";
import type { Lang, MatchSnapshot, Probs } from "../types";
import { reasonText } from "../words";

const SHOW_DECISION_MS = 7000;
const fill = (s: string, v: Record<string, string>) => s.replace(/\{(\w+)\}/g, (_, k) => v[k] ?? "");

/**
 * VAR check, both ways: while VAR reviews a goal, the Gaffer's Gauge shows what happens if it stands and if it's
 * ruled out. Then the decision shows for a few seconds.
 */
export function VarCheck({ snap, lang }: { snap: MatchSnapshot; lang: Lang }) {
  const v = snap.var;
  const d = snap.var_decision;
  const [, tick] = useState(0);
  const fresh = !!d && Date.now() - d.at < SHOW_DECISION_MS;
  useEffect(() => {
    if (!fresh || !d) return;
    const tm = window.setTimeout(() => tick((n) => n + 1), SHOW_DECISION_MS - (Date.now() - d.at) + 50);
    return () => window.clearTimeout(tm);
  }, [d?.at, fresh]); // eslint-disable-line react-hooks/exhaustive-deps

  if (v && v.status === "checking") {
    const team = v.team === 0 ? snap.home : snap.away;
    const side = v.team === 0 ? "home" : "away";
    return (
      <section className="card var checking" role="status" aria-live="polite">
        <div className="row">
          <span className="var-badge">VAR</span>
          <span className="eyebrow gold" style={{ flex: 1 }}>{t("varCheck", lang)} · {v.minute}'</span>
        </div>
        <p className="var-what">
          {fill(t("varChecking", lang), { reason: reasonText(v.reason, lang), player: v.player, team: team.name })}
        </p>
        <Scenario label={t("varIfStands", lang)} probs={v.stands} side={side} short={team.short} />
        <Scenario label={t("varIfOut", lang)} probs={v.ruled_out} side={side} short={team.short} />
      </section>
    );
  }

  if (d && fresh) {
    const stands = d.status === "stands";
    return (
      <section className={`card var decided ${stands ? "stands" : "out"}`} role="status" aria-live="polite">
        <span className="var-badge">VAR</span>
        <b>{stands ? t("varStands", lang) : fill(t("varRuledOut", lang), { reason: reasonText(d.reason, lang) })}</b>
      </section>
    );
  }
  return null;
}

function Scenario({ label, probs, side, short }: { label: string; probs: Probs; side: "home" | "away"; short: string }) {
  return (
    <div className="var-scn">
      <span className="var-lbl">{label}</span>
      <div className="meter-bar" aria-hidden="true">
        <div className="h" style={{ width: `${probs.home * 100}%` }} />
        <div className="d" style={{ width: `${probs.draw * 100}%` }} />
        <div className="a" style={{ width: `${probs.away * 100}%` }} />
      </div>
      <span className="var-pct"><b>{Math.round(probs[side] * 100)}%</b> {short}</span>
    </div>
  );
}
