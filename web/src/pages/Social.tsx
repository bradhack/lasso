import { useEffect, useState } from "react";
import { api } from "../api";
import { LANGS, t } from "../i18n";
import { useStore } from "../store";
import type { Lang, LeaderRow } from "../types";
import { Crest } from "../components/bits";
import { Flame } from "../components/Icons";
import { currentAppearance, setAppearance } from "../theme";

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
    const load = () => api.leaderboard(tab === "GLOBAL" ? undefined : tab).then((r) => alive && setRows(r.rows)).catch(() => undefined);
    load();
    const iv = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(iv);
    };
  }, [tab]);

  const refreshUser = async () => user && setUser(await api.user(user.id));

  return (
    <div className="page">
      <div className="hero">
        <span className="eyebrow gold">{t("leagues", lang)}</span>
        <h1>BRAGGING RIGHTS, <em>LIVE.</em></h1>
      </div>
      <div className="tabs" style={{ flexWrap: "wrap" }}>
        {[...codes, "GLOBAL"].map((c) => (
          <button key={c} className={`tab${tab === c ? " sel" : ""}`} onClick={() => setTab(c)} style={{ flex: "1 1 30%" }}>
            {c === "DIAMOND" ? "Diamond Dogs" : c === "GLOBAL" ? "Global" : c}
          </button>
        ))}
      </div>
      <section className="card">
        <div className="table">
          {rows.map((r) => (
            <div key={r.id} className={`trow${r.id === user?.id ? " me" : ""}`}>
              <span className={`rk r${r.rank}`}>{r.rank}</span>
              <span style={{ fontWeight: r.id === user?.id ? 700 : 500 }}>
                {r.id === user?.id ? `${r.name} (you)` : r.name}
                {r.streak >= 3 && <span style={{ color: "var(--gold-2)", marginLeft: 8, fontSize: 12 }}><Flame size={12} /> {r.streak}</span>}
              </span>
              <span className="num" style={{ fontSize: 20 }}>{r.biscuits.toLocaleString("en-US")}</span>
            </div>
          ))}
          {rows.length === 0 && <div className="empty">…</div>}
        </div>
      </section>
      <section className="card" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <span className="eyebrow">Start or join a league</span>
        <div style={{ display: "flex", gap: 8 }}>
          <input placeholder="League name" value={name} maxLength={32} onChange={(e) => setName(e.target.value)} aria-label="League name" />
          <button className="tab sel" style={{ flex: "0 0 96px", height: 46 }} onClick={async () => {
            if (!user) return;
            const l = await api.createLeague(user.id, name || `${user.name}'s league`);
            await refreshUser();
            setTab(l.code);
            toast({ kind: "mission", label: `Share code ${l.code} with your mates`, reward: 0 });
          }}>Create</button>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <input placeholder="Invite code" value={code} maxLength={8} onChange={(e) => setCode(e.target.value.toUpperCase())} aria-label="Invite code" />
          <button className="tab" style={{ flex: "0 0 96px", height: 46 }} onClick={async () => {
            if (!user || !code) return;
            try {
              const l = await api.joinLeague(user.id, code);
              await refreshUser();
              setTab(l.code);
            } catch (e) {
              toast({ kind: "error", text: (e as Error).message });
            }
          }}>Join</button>
        </div>
      </section>
    </div>
  );
}

export function CardsPage() {
  const user = useStore((s) => s.user);
  const lang = useStore((s) => s.lang);
  const cards = [...(user?.cards ?? [])].reverse();
  return (
    <div className="page">
      <div className="hero">
        <span className="eyebrow gold">{t("cards", lang)}</span>
        <h1>MOMENTS YOU <em>CALLED.</em></h1>
        <p>Bronze under 50%, silver under 25%, gold when the Gaffer gave it less than 10%.</p>
      </div>
      {cards.length === 0 ? <div className="card empty">{t("noCards", lang)}</div> : (
        <div className="mcards">
          {cards.map((c) => (
            <div key={c.id} className={`mcard ${c.rarity}`}>
              <span className="rar">{c.rarity.toUpperCase()}{c.rarity === "gold" ? " · BELIEVE" : ""}</span>
              <div>
                <div className="odds">{Math.round(c.p * 100)}%</div>
                <div className="title">{c.pick}</div>
              </div>
              <div className="meta">{c.title}<br />{c.match} · {c.minute}'</div>
            </div>
          ))}
        </div>
      )}
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
      <section className="card">
        <div className="row"><span className="eyebrow">Goldfish</span><span className="chip ghost">{user.goldfish_available ? "Ready" : "Used this week"}</span></div>
        <p className="muted" style={{ margin: "8px 0 0", fontSize: 13, lineHeight: 1.5 }}>Once a week, a missed call won't break a streak of 3 or more. Be a goldfish: forget it and go again.</p>
      </section>
      <section className="card" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <span className="eyebrow gold">{t("missions", lang)}</span>
        {user.missions.map((m) => (
          <div key={m.id} className={`mission${m.done ? " done" : ""}`}>
            <div className="row"><span>{m.label}</span><span className="muted">{m.done ? `+${m.reward}` : `${m.progress} / ${m.target}`}</span></div>
            <div className="bar"><span style={{ width: `${(m.progress / m.target) * 100}%` }} /></div>
          </div>
        ))}
      </section>
      <section className="card" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <span className="eyebrow">{t("settings", lang)}</span>
        <label className="f">{t("language", lang)}
          <select value={user.lang} onChange={(e) => updatePrefs({ lang: e.target.value as Lang })}>
            {LANGS.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
          </select>
        </label>
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
        </div>
        <label className="f">{t("yourClub", lang)}
          <select value={user.club_id ?? ""} onChange={(e) => updatePrefs({ club_id: e.target.value || null })}>
            <option value="">None</option>
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
