import { useEffect, useState } from "react";
import { api } from "../api";
import { t } from "../i18n";
import { useStore } from "../store";
import { useDialog } from "../useDialog";
import type { BigMoment, Lang } from "../types";
import { reasonText } from "../words";

const fill = (s: string, v: Record<string, string | number>) => s.replace(/\{(\w+)\}/g, (_, k) => String(v[k] ?? ""));

/** Start a private replay of a match from an elapsed minute, then open it. */
export async function startReplay(matchId: string, fromMinute: number): Promise<boolean> {
  const user = useStore.getState().user;
  if (!user) return false;
  try {
    const r = await api.replay(matchId, { user_id: user.id, from_minute: fromMinute });
    location.hash = `#/match/${r.room_id}`;
    return true;
  } catch {
    useStore.getState().toast({ kind: "error", text: "Couldn't start the replay. Try again in a moment." });
    return false;
  }
}

function label(m: BigMoment, lang: Lang, clubName: (id: string) => string) {
  const team = clubName(m.team_id);
  if (m.kind === "second_half") return t("bmSecondHalf", lang);
  if (m.kind === "red_card") return fill(t("bmRed", lang), { player: m.player, team });
  if (m.kind === "var") return fill(t("bmVar", lang), { player: m.player, reason: reasonText(m.reason, lang) });
  return fill(t(m.decision === "stands" ? "bmGoalVar" : "bmGoal", lang), { player: m.player, team });
}

/** Watch from the big moments: pick a goal, a red card or a VAR check and watch it play out in your own replay. */
export function BigMomentsSheet({ matchId, lang, onClose }: { matchId: string; lang: Lang; onClose: () => void }) {
  const panel = useDialog<HTMLDivElement>(onClose);
  const clubs = useStore((s) => s.clubs);
  const [list, setList] = useState<BigMoment[] | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  useEffect(() => {
    api.moments(matchId).then(setList).catch(() => setList([]));
  }, [matchId]);
  const go = async (start: number) => {
    setBusy(start);
    const ok = await startReplay(matchId, start);
    setBusy(null);
    if (ok) onClose();
  };
  const rows: { key: string; minute: number | null; text: string; start: number }[] = [
    { key: "ko", minute: null, text: t("bmKickoff", lang), start: 0 },
    ...(list ?? []).map((m, i) => ({ key: `${m.kind}-${i}`, minute: m.kind === "second_half" ? null : m.minute,
      text: label(m, lang, (id) => clubs[id]?.name ?? ""), start: m.start })),
  ];
  return (
    <div className="sheet" role="dialog" aria-modal="true" aria-labelledby="bm-title" onClick={onClose}>
      <div className="sheet-inner" ref={panel} tabIndex={-1} onClick={(e) => e.stopPropagation()}>
        <h2 id="bm-title" style={{ margin: 0, fontSize: 18 }}>{t("bmTitle", lang)}</h2>
        <p className="muted" style={{ margin: 0, fontSize: 13, lineHeight: 1.45 }}>{t("bmSub", lang)}</p>
        {list === null ? (
          <p className="muted" style={{ fontSize: 13 }}>…</p>
        ) : (
          <ul className="bm-list">
            {rows.map((r) => {
              const from = Math.max(0, (r.minute ?? (r.start > 44 ? 46 : 0)) - (r.minute ? 2 : 0));
              return (
                <li key={r.key}>
                  <button className="bm-row" onClick={() => go(r.start)} disabled={busy !== null}
                    aria-label={`${r.minute !== null ? `${r.minute}' ` : ""}${r.text}. ${fill(t("bmWatch", lang), { m: from })}`}>
                    <span className="bm-min" aria-hidden="true">{r.minute !== null ? `${r.minute}'` : "▶"}</span>
                    <span className="bm-text">{r.text}</span>
                    <span className="bm-go" aria-hidden="true">{busy === r.start ? t("bmStarting", lang) : fill(t("bmWatch", lang), { m: from })}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
        <button className="cta ghost" onClick={onClose}>{t("close", lang)}</button>
      </div>
    </div>
  );
}

/** The lobby card that opens the sheet for the showcase match. */
export function BigMomentsCard({ matchId, lang }: { matchId: string; lang: Lang }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="card bm-card" aria-labelledby="bm-card-title">
      <span id="bm-card-title" className="eyebrow gold">{t("bmTitle", lang)}</span>
      <p className="bm-lead">{t("bmLobby", lang)}</p>
      <button className="cta" onClick={() => setOpen(true)} aria-haspopup="dialog">{t("bmButton", lang)}</button>
      {open && <BigMomentsSheet matchId={matchId} lang={lang} onClose={() => setOpen(false)} />}
    </section>
  );
}

/** A link straight into a replay: #/replay/<match>/<minute> (after picking a name, for first-time visitors). */
export function ReplayGate({ matchId, minute, lang }: { matchId: string; minute?: string; lang: Lang }) {
  const user = useStore((s) => s.user);
  const [sheet, setSheet] = useState(false);
  useEffect(() => {
    if (!user) return;
    const m = Number(minute);
    if (minute !== undefined && Number.isFinite(m)) {
      startReplay(matchId, Math.max(0, Math.min(100, m))).then((ok) => { if (!ok) location.hash = "#/"; });
    } else {
      setSheet(true);
    }
  }, [user, matchId, minute]);
  return (
    <div className="page">
      <div className="empty">{t("bmStarting", lang)}</div>
      {sheet && <BigMomentsSheet matchId={matchId} lang={lang} onClose={() => { location.hash = "#/"; }} />}
    </div>
  );
}
