import { useEffect, useRef, useState } from "react";
import { t } from "../i18n";
import type { Key } from "../i18n";
import { useDialog } from "../useDialog";
import type { ClubRef, Lang, MatchSnapshot, Probs, Result, Season, SeasonOdds, TableRow, Zone } from "../types";
import { Crest } from "./bits";

const ZONE_LABEL: Record<Zone, Key> = { title: "zTitle", top4: "zTop4", relegation: "zRelegation" };
export const RACE_LABEL: Record<Zone, Key> = { title: "raceTitle", top4: "raceTop4", relegation: "raceRelegation" };
const fill = (s: string, v: Record<string, string | number>) => s.replace(/\{(\w+)\}/g, (_, k) => String(v[k] ?? ""));

export function ordinal(n: number, lang: Lang) {
  if (lang === "es") return `${n}.º`;
  if (lang === "pt") return `${n}º`;
  if (lang === "fr") return n === 1 ? "1er" : `${n}e`;
  const s = n % 100 >= 11 && n % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th";
  return `${n}${s}`;
}

/** Whole percentages, with "<1%" for the long shots rather than a misleading 0%. */
export function seasonPct(x: number) {
  if (x <= 0) return "0%";
  if (x < 0.005) return "<1%";
  if (x >= 1) return "100%";
  if (x > 0.995) return ">99%";
  return `${Math.round(x * 100)}%`;
}

/** Season odds right now: each result's odds weighted by the Gaffer's live chances of that result. */
function blend(season: Season, probs: Probs, club: string): SeasonOdds {
  const out = { title: 0, top4: 0, relegation: 0, avg_pos: 0 };
  for (const r of ["home", "draw", "away"] as Result[]) {
    const o = season.odds[r]?.[club];
    if (!o) continue;
    for (const k of Object.keys(out) as (keyof SeasonOdds)[]) out[k] += probs[r] * o[k];
  }
  return out;
}

/** The table with this match's current score counted, in order, with each club's position before it. */
function liveTable(season: Season, snap: MatchSnapshot) {
  const before = new Map(season.table.map((r, i) => [r.club_id, i + 1]));
  const counted = snap.status !== "scheduled";
  const [h, a] = snap.score;
  const rows: TableRow[] = season.table.map((r) => {
    const side = r.club_id === snap.home.club_id ? 0 : r.club_id === snap.away.club_id ? 1 : -1;
    if (side < 0 || !counted) return r;
    const f = side === 0 ? h : a;
    const g = side === 0 ? a : h;
    return {
      ...r, played: r.played + 1, gf: r.gf + f, ga: r.ga + g, gd: r.gd + f - g,
      pts: r.pts + (f > g ? 3 : f === g ? 1 : 0),
      won: r.won + (f > g ? 1 : 0), drawn: r.drawn + (f === g ? 1 : 0), lost: r.lost + (f < g ? 1 : 0),
    };
  });
  rows.sort((x, y) => y.pts - x.pts || y.gd - x.gd || y.gf - x.gf || x.name.localeCompare(y.name));
  return rows.map((r, i) => ({ ...r, pos: i + 1, was: before.get(r.club_id) ?? i + 1 }));
}

/** Season outlook: where both clubs stand in the table right now, and what this result means for their season. */
export function SeasonOutlook({ snap, lang }: { snap: MatchSnapshot; lang: Lang }) {
  const [open, setOpen] = useState(false);
  const season = snap.season;
  if (!season) {
    return (
      <section className="card season" aria-label={t("seasonTitle", lang)}>
        <span className="eyebrow gold">{t("seasonTitle", lang)}</span>
        <p className="muted" style={{ fontSize: 13, margin: "8px 0 0" }}>{t("seasonLoading", lang)}</p>
      </section>
    );
  }
  const table = liveTable(season, snap);
  const probs = snap.status === "scheduled" ? snap.prematch : snap.probs;
  return (
    <section className="card season" aria-labelledby="season-title">
      <div className="row">
        <span id="season-title" className="eyebrow gold">{t("seasonTitle", lang)} · {fill(t("matchday", lang), { n: season.matchday })}</span>
        <button className="linkbtn" onClick={() => setOpen(true)} aria-haspopup="dialog">{t("fullTable", lang)}</button>
      </div>
      {(["home", "away"] as const).map((side) => (
        <ClubStake key={side} side={side} club={snap[side]} season={season} probs={probs}
          row={table.find((r) => r.club_id === snap[side].club_id)!} lang={lang} />
      ))}
      {open && <TableSheet season={season} snap={snap} table={table} probs={probs} lang={lang} onClose={() => setOpen(false)} />}
    </section>
  );
}

function ClubStake({ side, club, season, probs, row, lang }: {
  side: "home" | "away"; club: ClubRef; season: Season; probs: Probs; row: TableRow & { pos: number; was: number }; lang: Lang;
}) {
  const zone = season.stakes[side]?.zone ?? "none";
  const now = blend(season, probs, club.club_id);
  const moved = row.was - row.pos;
  const flash = useFlash(row.pos);
  const win: Result = side;
  const lose: Result = side === "home" ? "away" : "home";
  const leading = probs[win] >= probs.draw && probs[win] >= probs[lose] ? win : probs.draw >= probs[lose] ? "draw" : lose;
  return (
    <div className="so-club">
      <div className="so-head">
        <Crest club={club} size="sm" round={side === "away"} />
        <b className="so-name">{club.name}</b>
        <span className={`so-pos${flash ? " flash" : ""}`} aria-label={`${fill(t("inTable", lang), { pos: ordinal(row.pos, lang) })}${moved ? `, ${fill(t(moved > 0 ? "upN" : "downN", lang), { n: Math.abs(moved) })}` : ""}`}>
          {ordinal(row.pos, lang)}
          {moved !== 0 && <i className={moved > 0 ? "up" : "down"} aria-hidden="true">{moved > 0 ? "▲" : "▼"}{Math.abs(moved)}</i>}
        </span>
      </div>
      {zone === "none" ? (
        <p className="so-mid">{fill(t("midTable", lang), { pos: ordinal(Math.round(now.avg_pos), lang) })}</p>
      ) : (
        <ZoneLine zone={zone} now={now[zone]} kickoff={season.kickoff[club.club_id]?.[zone]} lang={lang}
          outcomes={[
            ["ifWin", season.odds[win]?.[club.club_id]?.[zone], leading === win],
            ["ifDraw", season.odds.draw?.[club.club_id]?.[zone], leading === "draw"],
            ["ifLoss", season.odds[lose]?.[club.club_id]?.[zone], leading === lose],
          ]} />
      )}
    </div>
  );
}

function ZoneLine({ zone, now, kickoff, outcomes, lang }: {
  zone: Zone; now: number; kickoff?: number; outcomes: [Key, number | undefined, boolean][]; lang: Lang;
}) {
  const d = kickoff === undefined ? 0 : Math.round((now - kickoff) * 100);
  return (
    <>
      <div className="so-zone">
        <span className="so-zl">{t(ZONE_LABEL[zone], lang)}</span>
        <b className="so-now">{seasonPct(now)}</b>
        {d !== 0 && kickoff !== undefined && (
          <span className="so-delta">
            <i aria-hidden="true">{d > 0 ? "▲" : "▼"}</i> {fill(t("sinceKickoff", lang), { p: seasonPct(kickoff) })}
          </span>
        )}
      </div>
      <div className="so-ifs">
        {outcomes.map(([k, v, on]) => (
          <span key={k} className={`so-if${on ? " on" : ""}`}>
            {t(k, lang)} <b>{v === undefined ? "–" : seasonPct(v)}</b>
          </span>
        ))}
      </div>
    </>
  );
}

/** A short highlight when a club's live position changes (a goal moves the table). */
function useFlash(value: number) {
  const prev = useRef(value);
  const [on, setOn] = useState(false);
  useEffect(() => {
    if (prev.current === value) return;
    prev.current = value;
    setOn(true);
    const tm = window.setTimeout(() => setOn(false), 2400);
    return () => window.clearTimeout(tm);
  }, [value]);
  return on;
}

function TableSheet({ season, snap, table, probs, lang, onClose }: {
  season: Season; snap: MatchSnapshot; table: (TableRow & { pos: number; was: number })[]; probs: Probs; lang: Lang; onClose: () => void;
}) {
  const panel = useDialog<HTMLDivElement>(onClose);
  const live = new Set([snap.home.club_id, snap.away.club_id]);
  const n = table.length;
  return (
    <div className="sheet" role="dialog" aria-modal="true" aria-labelledby="table-title" onClick={onClose}>
      <div className="sheet-inner season-sheet" ref={panel} tabIndex={-1} onClick={(e) => e.stopPropagation()}>
        <div className="row">
          <h2 id="table-title" style={{ margin: 0, fontSize: 18 }}>{t("tableTitle", lang)}</h2>
          <span className="muted" style={{ fontSize: 12 }}>{fill(t("matchday", lang), { n: season.matchday })}</span>
        </div>
        <div className="lt-wrap" tabIndex={0} role="region" aria-labelledby="table-title">
          <table className="lt">
            <thead>
              <tr>
                <th scope="col" className="c-pos">#</th>
                <th scope="col" className="c-club">{t("colClub", lang)}</th>
                <th scope="col"><abbr title={t("colPlayed", lang)}>{t("colP", lang)}</abbr></th>
                <th scope="col"><abbr title={t("colGoalDiff", lang)}>{t("colGD", lang)}</abbr></th>
                <th scope="col"><abbr title={t("colPoints", lang)}>{t("colPts", lang)}</abbr></th>
                <th scope="col"><abbr title={t("colTitleLong", lang)}>{t("colTitle", lang)}</abbr></th>
                <th scope="col"><abbr title={t("colTop4Long", lang)}>{t("colTop4", lang)}</abbr></th>
                <th scope="col"><abbr title={t("colRelLong", lang)}>{t("colRel", lang)}</abbr></th>
              </tr>
            </thead>
            <tbody>
              {table.map((r) => {
                const o = blend(season, probs, r.club_id);
                const moved = r.was - r.pos;
                const cls = [live.has(r.club_id) ? "live" : "", r.pos === 4 ? "cut" : "", r.pos === n - 3 ? "cut" : ""].join(" ").trim();
                return (
                  <tr key={r.club_id} className={cls}>
                    <td className="c-pos">{r.pos}{moved !== 0 && <i className={moved > 0 ? "up" : "down"} aria-label={fill(t(moved > 0 ? "upN" : "downN", lang), { n: Math.abs(moved) })}>{moved > 0 ? "▲" : "▼"}</i>}</td>
                    <th scope="row" className="c-club">
                      <i className="lt-dot" style={{ background: r.primary }} aria-hidden="true" />
                      <span>{r.name}</span>
                      {live.has(r.club_id) && snap.status !== "finished" && snap.status !== "scheduled" && <span className="sr-only"> ({t("liveRow", lang)})</span>}
                    </th>
                    <td>{r.played}</td>
                    <td>{r.gd > 0 ? `+${r.gd}` : r.gd}</td>
                    <td className="c-pts">{r.pts}</td>
                    <td>{seasonPct(o.title)}</td>
                    <td>{seasonPct(o.top4)}</td>
                    <td>{seasonPct(o.relegation)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="muted" style={{ fontSize: 12, lineHeight: 1.45, margin: "12px 0 0" }}>
          {fill(t("seasonHow", lang), { n: season.sims.toLocaleString(lang === "en" ? "en-US" : lang) })}
        </p>
        <button className="cta" style={{ marginTop: 14 }} onClick={onClose}>{t("close", lang)}</button>
      </div>
    </div>
  );
}
