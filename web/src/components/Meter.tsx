import { useMemo } from "react";
import { t } from "../i18n";
import type { Lang, MatchSnapshot, MeterPoint } from "../types";
import { pct } from "./bits";

const HOME = "#D3D7DE";
const AWAY = "#8E7398";

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
      <div className="meter-bar" role="img" aria-label={`${snap.home.name} ${pct(p.home)}, draw ${pct(p.draw)}, ${snap.away.name} ${pct(p.away)}`}>
        <div className="h" style={{ width: `${p.home * 100}%` }} />
        <div className="d" style={{ width: `${p.draw * 100}%` }} />
        <div className="a" style={{ width: `${p.away * 100}%`, background: AWAY }} />
      </div>
      <div className="meter-nums">
        <div>
          <div className="v">{pct(p.home)}</div>
          <div className="l">{snap.home.name}</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div className="v" style={{ color: "#C9BCCF" }}>{pct(p.draw)}</div>
          <div className="l">{t("draw", lang)}</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div className="v" style={{ color: "#C9BCCF" }}>{pct(p.away)}</div>
          <div className="l">{snap.away.name}</div>
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
  const path = (k: "home" | "away") =>
    history.map((pt, i) => `${i ? "L" : "M"}${((pt.elapsed / maxX) * 100).toFixed(2)},${(30 - pt[k] * 30).toFixed(2)}`).join(" ");
  return (
    <svg className="spark" viewBox="0 -1 100 32" preserveAspectRatio="none" role="img" aria-label="Win chance over the match">
      <line x1="0" y1="15" x2="100" y2="15" stroke="#3D2447" strokeWidth="1" vectorEffect="non-scaling-stroke" strokeDasharray="2 4" />
      <path d={path("away")} fill="none" stroke={AWAY} strokeWidth="2" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
      <path d={path("home")} fill="none" stroke={HOME} strokeWidth="2.5" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
    </svg>
  );
}
