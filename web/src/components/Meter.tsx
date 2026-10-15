import { useMemo } from "react";
import { t } from "../i18n";
import type { Lang, MatchSnapshot, MeterPoint } from "../types";
import { pct } from "./bits";

const HOME = "var(--home)";
const AWAY = "var(--away)";

export function Meter({ snap, lang, compact = false }: { snap: MatchSnapshot; lang: Lang; compact?: boolean }) {
  const p = snap.probs;
  const last = snap.moments[snap.moments.length - 1];
  const sinceMin = last ? last.minute : 0;
  const ref = useMemo(() => pointAtOrBefore(snap.history, last), [snap.history, last]);
  const deltaH = ref ? Math.round((p.home - ref.home) * 100) : 0;
  const deltaA = ref ? Math.round((p.away - ref.away) * 100) : 0;
  const lead = Math.abs(deltaH) >= Math.abs(deltaA) ? { team: snap.home.name, d: deltaH } : { team: snap.away.name, d: deltaA };

  return (
    <div>
      <div className="row" style={{ marginTop: compact ? 0 : 18, alignItems: "baseline" }}>
        <span className="eyebrow">{t("meter", lang)}</span>
        {Math.abs(lead.d) >= 3 && (
          <span className="chip">
            {lead.team} {lead.d > 0 ? "+" : ""}
            {lead.d} {lang === "en" ? "since" : "·"} {sinceMin}'
          </span>
        )}
      </div>
      <div className={`meter-bar${compact ? "" : " big"}`} role="img" aria-label={`${snap.home.name} ${pct(p.home)}, draw ${pct(p.draw)}, ${snap.away.name} ${pct(p.away)}`}>
        <div className="h" style={{ width: `${p.home * 100}%` }} />
        <div className="d" style={{ width: `${p.draw * 100}%` }} />
        <div className="a" style={{ width: `${p.away * 100}%` }} />
      </div>
      <div className={`meter-nums${compact ? "" : " big"}`}>
        <div>
          <div className="v">{pct(p.home)}</div>
          <div className="l"><i className="key h" />{snap.home.name}</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div className="v" style={{ color: "var(--soft)" }}>{pct(p.draw)}</div>
          <div className="l"><i className="key d" />{t("draw", lang)}</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div className="v" style={{ color: "var(--soft)" }}>{pct(p.away)}</div>
          <div className="l"><i className="key a" />{snap.away.name}</div>
        </div>
      </div>
      {!compact && snap.history.length > 2 && <Spark history={snap.history} />}
    </div>
  );
}

function pointAtOrBefore(h: MeterPoint[], m?: { minute: number }) {
  if (!m || !h.length) return h[0];
  let best = h[0];
  for (const pt of h) {
    const minute = pt.period === 1 ? pt.clock : Math.max(pt.clock, 45);
    if (minute <= m.minute) best = pt;
  }
  return best;
}

function Spark({ history: raw }: { history: MeterPoint[] }) {
  // Snapshot and live pushes can overlap; plot one point per moment of match time, in order.
  const byTime = new Map<number, MeterPoint>();
  for (const pt of raw) byTime.set(pt.elapsed, pt);
  const history = [...byTime.values()].sort((a, b) => a.elapsed - b.elapsed);
  const maxX = Math.max(96, history[history.length - 1].elapsed);
  const x = (pt: MeterPoint) => ((pt.elapsed / maxX) * 100).toFixed(2);
  // A 100% stacked river: home on top, the draw in the middle, away below, matching the bar.
  const band = (lo: (pt: MeterPoint) => number, hi: (pt: MeterPoint) => number) => {
    const top = history.map((pt) => `${x(pt)},${(hi(pt) * 40).toFixed(2)}`);
    const bottom = [...history].reverse().map((pt) => `${x(pt)},${(lo(pt) * 40).toFixed(2)}`);
    return `M${top.join(" L")} L${bottom.join(" L")} Z`;
  };
  const end = x(history[history.length - 1]);
  return (
    <svg className="spark" viewBox="0 0 100 40" preserveAspectRatio="none" role="img" aria-label="Win chance over the match">
      <path d={band(() => 0, (pt) => pt.home)} style={{ fill: HOME }} />
      <path d={band((pt) => pt.home, (pt) => pt.home + pt.draw)} style={{ fill: "var(--draw-bar)" }} />
      <path d={band((pt) => pt.home + pt.draw, () => 1)} style={{ fill: AWAY }} />
      <line x1={end} y1="0" x2={end} y2="40" style={{ stroke: "var(--bg)" }} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
      <rect x={end} y="0" width={100 - Number(end)} height="40" style={{ fill: "var(--surface-3)", opacity: 0.35 }} />
    </svg>
  );
}
