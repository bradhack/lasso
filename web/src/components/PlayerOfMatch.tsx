import { useState } from "react";
import { t } from "../i18n";
import type { Key } from "../i18n";
import { useStore } from "../store";
import type { ImpactPlayer, Lang, MatchSnapshot } from "../types";
import { Trophy } from "./Icons";

const MOTM_REWARD = 30;
const TEAM = ["var(--home)", "var(--away)"];
const fill = (s: string, v: Record<string, string | number>) => s.replace(/\{(\w+)\}/g, (_, k) => String(v[k] ?? ""));
const pctText = (x: number) => `${Math.round(x * 100)}%`;
const signed = (x: number) => `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(Math.round(x))}`;

/** What a player did, in a few words: "1 goal · 2 chances". */
function did(p: ImpactPlayer, lang: Lang) {
  const parts: string[] = [];
  const add = (n: number, one: Key, many: Key) => n > 0 && parts.push(n === 1 ? t(one, lang) : fill(t(many, lang), { n }));
  add(p.goals, "impGoal1", "impGoalN");
  add(p.assists, "impAssist1", "impAssistN");
  add(p.saves, "impSave1", "impSaveN");
  add(p.shots, "impShot1", "impShotN");
  if (p.reds) parts.push(t("impRed", lang));
  return parts.join(" · ");
}

/** Player of the Match by impact: a live leaderboard of whose actions moved the chances most, and a fan vote. */
export function PlayerOfMatch({ snap, lang }: { snap: MatchSnapshot; lang: Lang }) {
  const [how, setHow] = useState(false);
  const pick = useStore((s) => s.motmPicks[snap.match_id]) || snap.impact?.mine || "";
  const vote = useStore((s) => s.voteMotm);
  const imp = snap.impact;
  const players = imp?.players ?? [];
  const max = Math.max(1, ...players.map((p) => Math.abs(p.impact)));
  const finished = snap.status === "finished";
  const open = !!imp?.open && !finished;
  const showVotes = !!pick || finished;
  const winner = players.find((p) => p.id === imp?.winner) ?? null;
  const fav = players.length ? players.reduce((a, b) => ((imp?.votes[b.id] ?? 0) > (imp?.votes[a.id] ?? 0) ? b : a)) : null;
  const picked = players.find((p) => p.id === pick);

  if (!finished && !open) {
    // First half: just a line, until there's a vote to cast.
    const lead = players[0];
    return (
      <section className="card motm compact" aria-labelledby="motm-title">
        <div className="row">
          <span id="motm-title" className="eyebrow gold">{t("motmTitle", lang)} · {t("motmBy", lang)}</span>
          <button className="linkbtn" onClick={() => setHow(!how)} aria-expanded={how} aria-controls="motm-how">{t("motmHow", lang)}</button>
        </div>
        {how && <p id="motm-how" className="motm-how">{t("motmExplain", lang)}</p>}
        <p className="motm-teaser">
          {lead && lead.impact > 0 ? `${fill(t("motmLeads", lang), { player: lead.name, pts: signed(lead.impact) })} ` : ""}
          {t("motmVoteSoon", lang)}
        </p>
      </section>
    );
  }

  return (
    <section className="card motm" aria-labelledby="motm-title">
      <div className="row">
        <span id="motm-title" className="eyebrow gold">{t("motmTitle", lang)} · {t("motmBy", lang)}</span>
        <button className="linkbtn" onClick={() => setHow(!how)} aria-expanded={how} aria-controls="motm-how">{t("motmHow", lang)}</button>
      </div>
      {how && <p id="motm-how" className="motm-how">{t("motmExplain", lang)}</p>}
      {finished && winner && (
        <div className="motm-winner" role="status">
          <Trophy size={20} />
          <b>{fill(t("motmWinner", lang), { player: winner.name })}</b>
        </div>
      )}
      {players.length === 0 ? (
        <p className="muted" style={{ fontSize: 13, margin: "8px 0 0" }}>{t("motmEmpty", lang)}</p>
      ) : (
        <ol className="motm-list">
          {players.map((p, i) => {
            const club = p.team === 0 ? snap.home : snap.away;
            const share = imp?.votes[p.id] ?? 0;
            const body = (
              <>
                <span className="motm-rank" aria-hidden="true">{i + 1}</span>
                <span className="motm-who">
                  <b>{p.name}{p.id === imp?.winner && <Trophy size={13} />}</b>
                  <small><i style={{ background: TEAM[p.team] }} aria-hidden="true" />{club.short}{did(p, lang) ? ` · ${did(p, lang)}` : ""}</small>
                  <span className="motm-bar" aria-hidden="true"><span style={{ width: `${(Math.max(0, p.impact) / max) * 100}%`, background: TEAM[p.team] }} /></span>
                </span>
                <span className="motm-pts">
                  <b aria-label={fill(t("impPts", lang), { n: signed(p.impact) })}>{signed(p.impact)}</b>
                  {showVotes && <small>{pctText(share)} <span className="sr-only">{t("motmVotes", lang)}</span></small>}
                </span>
              </>
            );
            const cls = `motm-row${p.id === pick ? " picked" : ""}${p.id === imp?.winner ? " won" : ""}`;
            return (
              <li key={p.id}>
                {open ? (
                  <button className={cls} onClick={() => vote(snap.match_id, p.id)} aria-pressed={p.id === pick}
                    aria-label={`${fill(t("motmVoteFor", lang), { player: p.name })}, ${club.name}, ${fill(t("impPts", lang), { n: signed(p.impact) })}${showVotes ? `, ${pctText(share)} ${t("motmVotes", lang)}` : ""}`}>
                    {body}
                  </button>
                ) : (
                  <div className={cls}>{body}</div>
                )}
              </li>
            );
          })}
        </ol>
      )}
      <p className="motm-foot" aria-live="polite">
        {finished
          ? fav && fill(t("motmFans", lang), { player: fav.name, p: pctText(imp?.votes[fav.id] ?? 0) })
          : open
            ? picked
              ? fill(t("motmYourPick", lang), { player: picked.name, n: (imp?.voters ?? 0).toLocaleString() })
              : fill(t("motmVoteHint", lang), { n: MOTM_REWARD })
            : players.length > 0 && t("motmVoteSoon", lang)}
      </p>
    </section>
  );
}
