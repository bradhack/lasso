import { useEffect } from "react";
import { Crest, pct } from "../components/bits";
import { CallIt } from "../components/CallIt";
import { Back, Chevron } from "../components/Icons";
import { Meter } from "../components/Meter";
import { Feed, StatsPanel } from "../components/Panels";
import { WhyItMoved } from "../components/WhyItMoved";
import { t } from "../i18n";
import { useStore } from "../store";
import type { Lang, MatchSummary } from "../types";

function statusLabel(m: MatchSummary, lang: Lang) {
  if (m.status === "finished") return t("fullTime", lang);
  if (m.status === "half_time") return t("halfTime", lang);
  if (m.status === "scheduled") return t("upNext", lang);
  return `${m.minute}'`;
}

export function Lobby() {
  const matches = useStore((s) => s.matches);
  const lang = useStore((s) => s.lang);
  const live = matches.filter((m) => m.status === "live" || m.status === "half_time");
  const other = matches.filter((m) => !(m.status === "live" || m.status === "half_time"));
  return (
    <div className="page">
      <div className="hero">
        <span className="eyebrow gold">{t("liveNow", lang)}</span>
        <h1>SEE WHY THE ODDS MOVED. <em>THEN OUT-PREDICT THE GAFFER.</em></h1>
        <p>Every chance, card and goal moves the Believe-o-Meter. AI agents explain why, then challenge you to call what's next.</p>
      </div>
      {[...live, ...other].map((m) => (
        <a key={m.match_id} className="card matchcard" href={`#/match/${m.match_id}`}>
          <div className="row">
            <span className="eyebrow">Synthetic League · MD {m.match_id.split("-MD")[1]?.slice(0, 2)}</span>
            <span style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 700, fontSize: 13 }}>
              {(m.status === "live") && <i className="dot pulse" />}
              {statusLabel(m, lang)}
            </span>
          </div>
          <div className="teams">
            <span style={{ display: "flex", alignItems: "center", gap: 10 }}><Crest club={m.home} size="sm" />{m.home.name}</span>
            <span className="g">{m.score[0]}</span>
            <span style={{ display: "flex", alignItems: "center", gap: 10 }}><Crest club={m.away} size="sm" round />{m.away.name}</span>
            <span className="g">{m.score[1]}</span>
          </div>
          <div className="meter-bar" style={{ height: 6 }}>
            <div className="h" style={{ width: `${m.probs.home * 100}%` }} />
            <div className="d" style={{ width: `${m.probs.draw * 100}%` }} />
            <div className="a" style={{ width: `${m.probs.away * 100}%`, background: "#8E7398" }} />
          </div>
          <div className="row" style={{ marginTop: 8, fontSize: 12 }}>
            <span className="muted">{pct(m.probs.home)} · {pct(m.probs.draw)} · {pct(m.probs.away)}</span>
            <span style={{ display: "flex", alignItems: "center", gap: 4, color: "#D8B26E", fontWeight: 700 }}>
              {t("callIt", lang)} <Chevron size={14} />
            </span>
          </div>
        </a>
      ))}
    </div>
  );
}

export function MatchPage({ id }: { id: string }) {
  const snap = useStore((s) => s.snapshots[id]);
  const watch = useStore((s) => s.watch);
  const unwatch = useStore((s) => s.unwatch);
  const lang = useStore((s) => s.lang);
  const user = useStore((s) => s.user);
  const connected = useStore((s) => s.connected);

  useEffect(() => {
    watch(id).catch(() => undefined);
    return () => unwatch(id);
  }, [id, connected, watch, unwatch]);

  if (!snap) return <div className="page"><div className="empty">…</div></div>;
  const moment = [...snap.moments].reverse().find((m) => m.trigger !== "kickoff") ?? snap.moments[snap.moments.length - 1];

  return (
    <div className="page">
      <section className="card">
        <div className="row" style={{ fontSize: 12 }}>
          <a href="#/" aria-label="Back to live matches" style={{ display: "flex", alignItems: "center", color: "#A99AB0" }}>
            <Back size={18} /> <span className="eyebrow" style={{ marginLeft: 4 }}>Synthetic League</span>
          </a>
          <span style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 700 }}>
            {snap.status === "live" && <i className="dot pulse" />}
            {statusLabel(snap, lang)}
          </span>
        </div>
        <div className="scoreboard">
          <div className="team"><Crest club={snap.home} />{snap.home.name}{snap.reds[0] > 0 && <span>{Array.from({ length: snap.reds[0] }, (_, i) => <i key={i} className="reds" />)}</span>}</div>
          <div className="score" aria-label={`${snap.score[0]} to ${snap.score[1]}`}>{snap.score[0]}<span className="sep">:</span>{snap.score[1]}</div>
          <div className="team"><Crest club={snap.away} round />{snap.away.name}{snap.reds[1] > 0 && <span>{Array.from({ length: snap.reds[1] }, (_, i) => <i key={i} className="reds" />)}</span>}</div>
        </div>
        <Meter snap={snap} lang={lang} />
      </section>
      {moment && <WhyItMoved snap={snap} moment={moment} lang={lang} />}
      <CallIt snap={snap} lang={lang} />
      {user?.persona === "analyst" && <StatsPanel snap={snap} lang={lang} />}
      <Feed snap={snap} lang={lang} />
      {user?.persona !== "analyst" && <StatsPanel snap={snap} lang={lang} />}
    </div>
  );
}
