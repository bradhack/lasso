import { t } from "../i18n";
import type { Key } from "../i18n";
import { feedText } from "../words";
import type { Lang, MatchSnapshot } from "../types";

export function Feed({ snap, lang }: { snap: MatchSnapshot; lang: Lang }) {
  const items = [...snap.feed].reverse().slice(0, 12);
  return (
    <section className="card">
      <span className="eyebrow">{t("feed", lang)}</span>
      <div className="feed" style={{ marginTop: 12 }}>
        {items.length === 0 && <div className="empty">…</div>}
        {items.map((f) => (
          <div key={f.seq} className={`feed-item ${f.type}`}>
            <span className="min">{f.minute}'</span>
            <span>{feedText(f, snap, lang)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

type StatKey = keyof MatchSnapshot["stats"]["teams"][0];

/** Each stat: how to show it, and how big a gap has to be before one side really leads (smaller is "even"). */
const ROWS: { key: StatKey; label: Key | "xG"; fmt?: (v: number) => string; even: number; unit?: string }[] = [
  { key: "xg", label: "xG", fmt: (v) => v.toFixed(2), even: 0.1 },
  { key: "xg_last_10", label: "sXgLast10", fmt: (v) => v.toFixed(2), even: 0.1 },
  { key: "possession", label: "sPossession", even: 3 },
  { key: "field_tilt", label: "sFieldTilt", even: 3 },
  { key: "shots", label: "sShots", even: 1 },
  { key: "pass_accuracy", label: "sPassAcc", even: 3 },
  { key: "avg_pass_difficulty", label: "sPassDiff", fmt: (v) => v.toFixed(2), even: 0.02 },
  { key: "fastest_shot_kmh", label: "sFastest", fmt: (v) => v.toFixed(0), even: 3 },
];

const fill = (s: string, v: Record<string, string | number>) => s.replace(/\{(\w+)\}/g, (_, k) => String(v[k] ?? ""));

/** One sentence on who's on top: territory (field tilt) and chances (xG), only where the gap is real. */
function headline(snap: MatchSnapshot, lang: Lang) {
  const [h, a] = snap.stats.teams;
  const names = [snap.home.name, snap.away.name];
  const tLead = h.field_tilt - a.field_tilt >= 10 ? 0 : a.field_tilt - h.field_tilt >= 10 ? 1 : null;
  const hx = h.xg, ax = a.xg;
  const xLead = hx - ax >= 0.25 && hx >= 1.3 * ax ? 0 : ax - hx >= 0.25 && ax >= 1.3 * hx ? 1 : null;
  const v = {
    t1: tLead !== null ? names[tLead] : "", tilt: tLead === 0 ? h.field_tilt : a.field_tilt,
    t2: xLead !== null ? names[xLead] : "",
    x1: (xLead === 1 ? ax : hx).toFixed(2), x2: (xLead === 1 ? hx : ax).toFixed(2),
  };
  if (tLead !== null && xLead !== null) return fill(t(tLead === xLead ? "shBoth" : "shSplit", lang), v);
  if (tLead !== null) return fill(t("shTilt", lang), { ...v, x1: hx.toFixed(2), x2: ax.toFixed(2) });
  if (xLead !== null) return fill(t("shXg", lang), v);
  return t("shEven", lang);
}

export function StatsPanel({ snap, lang }: { snap: MatchSnapshot; lang: Lang }) {
  const [h, a] = snap.stats.teams;
  const shorts = [snap.home.short, snap.away.short];
  return (
    <section className="card stats-card" aria-label={t("analyst", lang)}>
      <div className="row">
        <span className="eyebrow">{t("analyst", lang)}</span>
        <span className="muted" style={{ fontSize: 12 }}>{snap.home.short} · {snap.away.short}</span>
      </div>
      <p className="stats-head">{headline(snap, lang)}</p>
      <div style={{ display: "flex", flexDirection: "column", gap: 14, marginTop: 10 }}>
        {ROWS.map((r) => {
          const hv = Number(h[r.key]) || 0, av = Number(a[r.key]) || 0;
          const fmt = r.fmt ?? ((v: number) => String(v));
          const gap = hv - av;
          const even = Math.abs(gap) < r.even;
          const lead = gap > 0 ? 0 : 1;
          // How far the bar reaches from the center: the leader's share above 50%, scaled to half the track.
          const share = hv + av > 0 ? Math.max(hv, av) / (hv + av) : 0.5;
          const reach = even ? 0 : Math.min(1, (share - 0.5) / 0.5);
          const label = r.label === "xG" ? "xG" : t(r.label, lang);
          const tag = even ? t("statEven", lang) : `${shorts[lead]} +${fmt(Math.abs(gap))}`;
          return (
            <div className={`stat${even ? " even" : ""}`} key={r.key}>
              <span className="v">{fmt(hv)}</span>
              <span className="lbl">{label}<small className="gap">{tag}</small></span>
              <span className="v r">{fmt(av)}</span>
              <div className="dbar" aria-hidden="true">
                <i className="mid" />
                {!even && (
                  <span style={{ [lead === 0 ? "right" : "left"]: "50%", width: `${Math.max(4, reach * 50)}%`,
                    background: lead === 0 ? "var(--home)" : "var(--away)" }} />
                )}
              </div>
            </div>
          );
        })}
      </div>
      <p className="stats-note">{t("tiltNote", lang)}</p>
    </section>
  );
}
