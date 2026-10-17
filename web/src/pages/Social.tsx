import { useEffect, useState } from "react";
import { api } from "../api";
import { HTML_LANG, LANGS, t } from "../i18n";
import type { Key } from "../i18n";
import { Listen } from "../components/Listen";
import { useStore } from "../store";
import type { Lang, LeaderRow, VoiceOption } from "../types";
import { Crest } from "../components/bits";
import { Fish, Flame } from "../components/Icons";
import { StickerBadge, stickerText } from "../components/Stickers";
import { currentAppearance, setAppearance } from "../theme";
import { marketQuestion, missionLabel, optionLabel } from "../words";

/** Listen's voice for the fan's language: accent and man or woman, with a sample to hear first. Shown only when
 * the server reads aloud (the phone's own voice has no choice to offer). */
function VoicePicker({ lang }: { lang: Lang }) {
  const azure = useStore((s) => s.speechAzure);
  const options = useStore((s) => s.voices[lang]) ?? [];
  const picked = useStore((s) => s.voicePick[lang]);
  const setVoice = useStore((s) => s.setVoice);
  if (!azure || options.length < 2) return null;
  const value = options.find((v) => v.id === picked)?.id ?? options[0].id;
  const label = (v: VoiceOption) =>
    `${t(`acc_${v.accent}` as Key, lang)} · ${t(`gen_${v.gender}` as Key, lang)}`;
  return (
    <div className="f voice-pick">
      <label htmlFor="settings-voice">{t("voiceLabel", lang)}</label>
      <div className="voice-row">
        <select id="settings-voice" name="voice" value={value} onChange={(e) => setVoice(lang, e.target.value)}>
          {options.map((v) => <option key={v.id} value={v.id}>{label(v)}</option>)}
        </select>
        <Listen kind="sample" id="1" lang={lang} text={t("voiceTry", lang)} label={t("voiceTry", lang)} />
      </div>
      <span className="voice-hint">{t("voiceHint", lang)}</span>
    </div>
  );
}

export function Leagues() {
  const user = useStore((s) => s.user);
  const lang = useStore((s) => s.lang);
  const toast = useStore((s) => s.toast);
  const setUser = useStore((s) => s.setUser);
  const [tab, setTab] = useState<string>("DIAMOND");
  const [rows, setRows] = useState<LeaderRow[]>([]);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const codes = user?.leagues ?? ["DIAMOND"];

  useEffect(() => {
    let alive = true;
    const load = () => api.leaderboard(tab === "GLOBAL" ? undefined : tab, user?.id).then((r) => alive && setRows(r.rows)).catch(() => undefined);
    load();
    const iv = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(iv);
    };
  }, [tab, user?.id]);

  const refreshUser = async () => user && setUser(await api.user(user.id));

  return (
    <div className="page">
      <div className="hero">
        <span className="eyebrow gold">{t("leagues", lang)}</span>
        <h1>{t("lgHero1", lang)} <em>{t("lgHero2", lang)}</em></h1>
      </div>
      <div className="tabs" style={{ flexWrap: "wrap" }}>
        {[...codes, "GLOBAL"].map((c) => (
          <button key={c} className={`tab${tab === c ? " sel" : ""}`} onClick={() => setTab(c)} style={{ flex: "1 1 30%" }}>
            {c === "DIAMOND" ? "Biscuit Box" : c === "GLOBAL" ? t("lgGlobal", lang) : c}
          </button>
        ))}
      </div>
      <section className="card">
        <div className="table">
          {rows.map((r) => (
            <div key={r.key} className={`trow${r.me ? " me" : ""}`}>
              <span className={`rk r${r.rank}`}>{r.rank}</span>
              <span style={{ fontWeight: r.me ? 700 : 500 }}>
                {r.me ? `${r.name} ${t("lgYou", lang)}` : r.name}
                {r.streak >= 3 && <span style={{ color: "var(--gold-2)", marginLeft: 8, fontSize: 12 }}><Flame size={12} /> {r.streak}</span>}
              </span>
              <span className="num" style={{ fontSize: 20 }}>{r.biscuits.toLocaleString(HTML_LANG[lang])}</span>
            </div>
          ))}
          {rows.length === 0 && <div className="empty">…</div>}
        </div>
      </section>
      <section className="card" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <span className="eyebrow">{t("lgStart", lang)}</span>
        <div style={{ display: "flex", gap: 8 }}>
          <input id="league-name" name="league_name" autoComplete="off" placeholder={t("lgName", lang)} value={name} maxLength={32} onChange={(e) => setName(e.target.value)} aria-label={t("lgName", lang)} />
          <button className="tab sel" style={{ flex: "0 0 96px", height: 46 }} onClick={async () => {
            if (!user) return;
            const l = await api.createLeague(user.id, name || t("lgDefault", lang).replace("{name}", user.name));
            await refreshUser();
            setTab(l.code);
            toast({ kind: "mission", label: t("lgShare", lang).replace("{code}", l.code), reward: 0 });
          }}>{t("lgCreate", lang)}</button>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <input id="invite-code" name="invite_code" autoComplete="off" autoCapitalize="characters" placeholder={t("lgCode", lang)} value={code} maxLength={8} onChange={(e) => setCode(e.target.value.toUpperCase())} aria-label={t("lgCode", lang)} />
          <button className="tab" style={{ flex: "0 0 96px", height: 46 }} onClick={async () => {
            if (!user || !code) return;
            try {
              const l = await api.joinLeague(user.id, code);
              await refreshUser();
              setTab(l.code);
            } catch (e) {
              toast({ kind: "error", text: (e as Error).message });
            }
          }}>{t("lgJoin", lang)}</button>
        </div>
      </section>
    </div>
  );
}

export function StickersPage() {
  const user = useStore((s) => s.user);
  const lang = useStore((s) => s.lang);
  const book = user?.stickers ?? [];
  const earned = book.filter((s) => s.earned).length;
  return (
    <div className="page">
      <div className="hero">
        <span className="eyebrow gold">{t("cards", lang)} · {earned} / {book.length}</span>
        <h1>{t("stickerHead", lang)}</h1>
        <p>{t("stickerSub", lang)}</p>
      </div>
      {(["gold", "silver", "bronze"] as const).map((tier) => (
        <section key={tier} className="card">
          <span className={`eyebrow tier-${tier}`}>{t(tier, lang)}</span>
          <div className="stickers">
            {book.filter((s) => s.tier === tier).map((s) => {
              const txt = stickerText(s, lang);
              return (
                <div key={s.id} className={`sticker${s.earned ? "" : " locked"}`}>
                  <StickerBadge s={s} />
                  <b>{txt.name}{s.count > 1 ? ` ×${s.count}` : ""}</b>
                  <span>{s.earned && s.detail ? s.detail : txt.how}</span>
                </div>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}

export function Profile() {
  const user = useStore((s) => s.user);
  const lang = useStore((s) => s.lang);
  const clubs = useStore((s) => s.clubs);
  const updatePrefs = useStore((s) => s.updatePrefs);
  const setUser = useStore((s) => s.setUser);
  const [appearance, setAppearanceState] = useState(currentAppearance);
  useEffect(() => {
    const sync = () => setAppearanceState(currentAppearance());
    window.addEventListener("lasso-theme", sync);
    return () => window.removeEventListener("lasso-theme", sync);
  }, []);
  useEffect(() => {
    if (user) api.user(user.id).then(setUser).catch(() => undefined);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  if (!user) return null;
  const prevLevelXp = 50 * (user.level - 1) ** 2;
  const progress = (user.xp - prevLevelXp) / Math.max(1, user.next_level_xp - prevLevelXp);
  const club = user.club_id ? clubs[user.club_id] : null;
  const winRate = user.calls_total ? Math.round((100 * user.calls_won) / user.calls_total) : 0;

  return (
    <div className="page">
      <section className="card">
        <div className="row">
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {club && <Crest club={club} />}
            <div>
              <div style={{ fontWeight: 700, fontSize: 18 }}>{user.name}</div>
              <div className="muted" style={{ fontSize: 13 }}>{club ? club.name : "No club yet"}</div>
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div className="eyebrow">{t("level", lang)}</div>
            <div className="num" style={{ fontSize: 34, lineHeight: 1 }}>{user.level}</div>
          </div>
        </div>
        <div className="xp"><span style={{ width: `${Math.min(100, progress * 100)}%` }} /></div>
        <div className="row muted" style={{ fontSize: 12, marginTop: 6 }}>
          <span>{user.xp} XP</span><span>Season pass · next tier at {user.next_level_xp} XP</span>
        </div>
      </section>
      <div className="statgrid">
        <div><div className="v">{user.streak}</div><div className="l">Current streak</div></div>
        <div><div className="v">{user.best_streak}</div><div className="l">Best streak</div></div>
        <div><div className="v">{winRate}%</div><div className="l">Calls won</div></div>
      </div>
      <section className={`card gfcard${user.goldfish_available ? "" : " used"}`}>
        <span className="fishbadge"><Fish size={30} /></span>
        <div>
          <b>{user.goldfish_available ? t("gfReady", lang) : t("gfUsed", lang)}</b>
          <p>{t("gfHow", lang)}</p>
        </div>
      </section>
      <CallHistory />
      <section className="card" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <span className="eyebrow gold">{t("missions", lang)}</span>
        {user.missions.map((m) => (
          <div key={m.id} className={`mission${m.done ? " done" : ""}`}>
            <div className="row"><span>{missionLabel(m.id, m.label, lang)}</span><span className="muted">{m.done ? `+${m.reward}` : `${m.progress} / ${m.target}`}</span></div>
            <div className="bar"><span style={{ width: `${(m.progress / m.target) * 100}%` }} /></div>
          </div>
        ))}
      </section>
      <section className="card" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <span className="eyebrow">{t("settings", lang)}</span>
        <label className="f">{t("language", lang)}
          <select id="settings-lang" name="lang" value={user.lang} onChange={(e) => updatePrefs({ lang: e.target.value as Lang })}>
            {LANGS.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
          </select>
        </label>
        <VoicePicker lang={lang} />
        <div className="f" style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, color: "var(--muted)" }}>{t("appearance", lang)}
          <div className="seg">
            <button className={`tab${appearance === "dark" ? " sel" : ""}`} onClick={() => { setAppearance("dark"); setAppearanceState("dark"); }}>{t("dark", lang)}</button>
            <button className={`tab${appearance === "light" ? " sel" : ""}`} onClick={() => { setAppearance("light"); setAppearanceState("light"); }}>{t("light", lang)}</button>
          </div>
        </div>
        <div className="f" style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, color: "var(--muted)" }}>{t("depth", lang)}
          <div className="seg">
            <button className={`tab${user.persona === "fan" ? " sel" : ""}`} onClick={() => updatePrefs({ persona: "fan" })}>{t("fan", lang)}</button>
            <button className={`tab${user.persona === "analyst" ? " sel" : ""}`} onClick={() => updatePrefs({ persona: "analyst" })}>{t("analystMode", lang)}</button>
          </div>
          <span style={{ fontSize: 12 }}>{t(user.persona === "fan" ? "fanHint" : "analystHint", lang)}</span>
        </div>
        <label className="f">{t("yourClub", lang)}
          <select id="settings-club" name="club" value={user.club_id ?? ""} onChange={(e) => updatePrefs({ club_id: e.target.value || null })}>
            <option value="">{t("clubNone", lang)}</option>
            {Object.values(clubs).map((c) => <option key={c.club_id} value={c.club_id}>{c.name}</option>)}
          </select>
        </label>
      </section>
      <p className="muted" style={{ fontSize: 12, textAlign: "center", lineHeight: 1.5 }}>
        Biscuits are free in-app points with no cash value. All clubs, players and matches are synthetic.
      </p>
    </div>
  );
}

/** Every call you've made, newest first, with where it stands now. */
function CallHistory() {
  const calls = useStore((s) => s.calls);
  const matches = useStore((s) => s.matches);
  const lang = useStore((s) => s.lang);
  const [all, setAll] = useState(false);
  const list = Object.values(calls).sort((a, b) => (b.placed_at ?? 0) - (a.placed_at ?? 0));
  const label = (id?: string) => {
    const m = matches.find((x) => x.match_id === (id ?? "").split(":")[0]);
    return m ? `${m.home.short} v ${m.away.short}` : "";
  };
  const won = list.filter((c) => c.status === "won").length;
  const open = list.filter((c) => c.status === "open").length;
  const shown = all ? list : list.slice(0, 8);
  return (
    <section className="card" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div className="row">
        <span className="eyebrow gold">{t("myCalls", lang)}</span>
        {list.length > 0 && (
          <span className="muted" style={{ fontSize: 12 }}>
            {t("callsSummary", lang).replace("{n}", String(list.length)).replace("{w}", String(won)).replace("{o}", String(open))}
          </span>
        )}
      </div>
      {list.length === 0 && <p className="muted" style={{ margin: 0, fontSize: 13 }}>{t("noCalls", lang)}</p>}
      {shown.map((c) => (
        <div key={c.id} className={`callrow ${c.status}${c.goldfish ? " saved" : ""}`}>
          <div className="q">
            <b>{marketQuestion(c, lang)}</b>
            <span>{optionLabel(c.kind, c.option_id, c.label, lang)} · {c.stake} @ {c.multiplier.toFixed(1)}x · {label(c.market_id)} {c.minute}'</span>
          </div>
          <span className="st">
            {c.status === "open" && t("stOpen", lang)}
            {c.status === "won" && `+${c.payout}`}
            {c.status === "lost" && (c.goldfish ? <><Fish size={14} /> {t("stLost", lang)}</> : t("stLost", lang))}
          </span>
        </div>
      ))}
      {list.length > 8 && !all && <button className="linkbtn" onClick={() => setAll(true)}>{t("showAll", lang)}</button>}
    </section>
  );
}
