import { useState } from "react";
import { LANGS, t } from "../i18n";
import { useStore } from "../store";
import type { Lang } from "../types";
import { Crest } from "./bits";
import { LassoMark } from "./Icons";

export function Onboarding() {
  const clubMap = useStore((s) => s.clubs);
  const clubs = Object.values(clubMap);
  const signUp = useStore((s) => s.signUp);
  const [name, setName] = useState("");
  const [club, setClub] = useState<string | null>(null);
  const [persona, setPersona] = useState<"fan" | "analyst">("fan");
  const [lang, setLang] = useState<Lang>(guessLang());
  const [busy, setBusy] = useState(false);

  return (
    <div className="sheet" role="dialog" aria-modal="true" aria-labelledby="ob-title">
      <div className="sheet-inner">
        <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--gold)" }}>
          <LassoMark size={34} />
          <span style={{ fontFamily: "Sora", fontWeight: 700, fontSize: 30, color: "var(--text)" }}>lasso</span>
        </div>
        <h2 id="ob-title" className="num" style={{ fontSize: 34, margin: 0, lineHeight: 1.05 }}>
          {t("heroA", lang)}<br /><span style={{ color: "var(--gold)" }}>{t("heroB", lang)}</span>
        </h2>
        <p className="muted" style={{ margin: 0, fontSize: 14, lineHeight: 1.5 }}>
          {t("obSub", lang)}
        </p>
        <label className="f">
          Your name
          <input value={name} maxLength={24} onChange={(e) => setName(e.target.value)} placeholder="Fan name" autoComplete="nickname" />
        </label>
        <div className="f" style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, color: "var(--muted)" }}>
          {t("yourClub", lang)} <span style={{ fontSize: 12 }}>{t("clubHint", lang)}</span>
          <div className="clubgrid">
            {clubs.map((c) => (
              <button key={c.club_id} className={`clubpick${club === c.club_id ? " sel" : ""}`} onClick={() => setClub(club === c.club_id ? null : c.club_id)} aria-pressed={club === c.club_id} title={c.name}>
                <Crest club={c} size="sm" />
                {c.short}
              </button>
            ))}
          </div>
        </div>
        <div className="f" style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, color: "var(--muted)" }}>
          {t("depth", lang)}
          <div className="seg">
            <button className={`tab${persona === "fan" ? " sel" : ""}`} onClick={() => setPersona("fan")}>{t("fan", lang)}</button>
            <button className={`tab${persona === "analyst" ? " sel" : ""}`} onClick={() => setPersona("analyst")}>{t("analystMode", lang)}</button>
          </div>
          <span style={{ fontSize: 12 }}>{t(persona === "fan" ? "fanHint" : "analystHint", lang)}</span>
        </div>
        <label className="f">
          {t("language", lang)}
          <select value={lang} onChange={(e) => setLang(e.target.value as Lang)}>
            {LANGS.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
          </select>
        </label>
        <button className="cta" disabled={busy} onClick={async () => { setBusy(true); await signUp(name.trim(), club, persona, lang); }}>
          {busy ? "…" : "Let's go"}
        </button>
      </div>
    </div>
  );
}

function guessLang(): Lang {
  const l = (navigator.language || "en").slice(0, 2);
  return (["en", "es", "pt", "fr"].includes(l) ? l : "en") as Lang;
}
