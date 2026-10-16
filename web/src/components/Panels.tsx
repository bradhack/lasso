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

const ROWS: { key: keyof MatchSnapshot["stats"]["teams"][0]; label: Key | "xG"; fmt?: (v: number) => string }[] = [
  { key: "xg", label: "xG", fmt: (v) => v.toFixed(2) },
  { key: "xg_last_10", label: "sXgLast10", fmt: (v) => v.toFixed(2) },
  { key: "possession", label: "sPossession" },
  { key: "field_tilt", label: "sFieldTilt" },
  { key: "shots", label: "sShots" },
  { key: "pass_accuracy", label: "sPassAcc" },
  { key: "avg_pass_difficulty", label: "sPassDiff", fmt: (v) => v.toFixed(2) },
  { key: "fastest_shot_kmh", label: "sFastest", fmt: (v) => v.toFixed(0) },
];

export function StatsPanel({ snap, lang }: { snap: MatchSnapshot; lang: Lang }) {
  const [h, a] = snap.stats.teams;
  return (
    <section className="card">
      <div className="row">
        <span className="eyebrow">{t("analyst", lang)}</span>
        <span className="muted" style={{ fontSize: 12 }}>{snap.home.short} · {snap.away.short}</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 12 }}>
        {ROWS.map((r) => {
          const hv = Number(h[r.key]) || 0, av = Number(a[r.key]) || 0;
          const total = hv + av || 1;
          const fmt = r.fmt ?? ((v: number) => String(v));
          return (
            <div className="stat" key={r.key}>
              <span className="v">{fmt(hv)}</span>
              <span className="lbl">{r.label === "xG" ? "xG" : t(r.label, lang)}</span>
              <span className="v r">{fmt(av)}</span>
              <div className="bars">
                <span style={{ flex: hv / total, background: "var(--home)" }} />
                <span style={{ flex: av / total, background: "var(--away)" }} />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
