import { loc, t } from "./i18n";
import type { Key } from "./i18n";
import type { FeedItem, Lang, Localized, MatchSummary } from "./types";

/**
 * Game and match text in the fan's language. The server sends what happened (a market's kind and team, an
 * event's type and player); the words are chosen here, so every language reads naturally.
 */

const fill = (s: string, vars: Record<string, string | number>) =>
  s.replace(/\{(\w+)\}/g, (_, k) => (k in vars ? String(vars[k]) : `{${k}}`));

type MarketLike = { kind?: string; params?: { team?: string; until?: number }; question: string };

export function marketQuestion(m: MarketLike, lang: Lang): string {
  const p = m.params ?? {};
  switch (m.kind) {
    case "score": return p.team && p.until ? fill(t("qScore", lang), { team: p.team, min: p.until }) : m.question;
    case "next": return t("qNext", lang);
    case "comeback": return p.team ? fill(t("qComeback", lang), { team: p.team }) : m.question;
    case "result": return t("qResult", lang);
    case "var": return t("qVar", lang);
    default: return m.question;
  }
}

/** Team names stay as they are; the yes/no style answers are translated. */
export function optionLabel(kind: string | undefined, id: string, fallback: string, lang: Lang): string {
  if (kind === "var") return t(id === "yes" ? "oStands" : "oRuledOut", lang);
  if (kind === "comeback") return t(id === "yes" ? "oBelieve" : "oNoWay", lang);
  if (id === "yes") return t("oYes", lang);
  if (id === "no") return t("oNo", lang);
  if (id === "none") return t("oNoMore", lang);
  if (id === "draw") return t("draw", lang);
  return fallback;
}

/** The Game Master's invitation: by language when the agents wrote it that way; English text only for English. */
export function marketCopy(copy: string | Localized | null | undefined, lang: Lang): string | null {
  if (!copy) return null;
  if (typeof copy === "string") return lang === "en" ? copy : null;
  return loc(copy, lang) || null;
}

const REASON: Record<string, Key> = { offside: "rOffside", handball: "rHandball", foul: "rFoul" };
export const reasonText = (reason: string | undefined, lang: Lang) => t(REASON[reason ?? "offside"] ?? "rOffside", lang);

export function feedText(f: FeedItem, m: MatchSummary, lang: Lang): string {
  const team = f.team === 0 ? m.home.name : f.team === 1 ? m.away.name : "";
  const v = { player: f.player, team, xg: (f.xg ?? 0).toFixed(2), reason: reasonText(f.reason, lang), off: f.off ?? "" };
  switch (f.type) {
    case "goal": return fill(t("fGoal", lang), v);
    case "shot": return fill(t(f.on ? "fChanceSaved" : "fChanceOff", lang), v);
    case "red_card": return fill(t("fRed", lang), v);
    case "yellow_card": return fill(t("fYellow", lang), v);
    case "substitution": return f.off ? fill(t("fSub", lang), v) : f.text;
    case "half_time": return fill(t("fHalf", lang), { h: f.score?.[0] ?? 0, a: f.score?.[1] ?? 0 });
    case "full_time": return fill(t("fFull", lang), { h: f.score?.[0] ?? 0, a: f.score?.[1] ?? 0 });
    case "var_check": return fill(t("fVarCheck", lang), v);
    case "var_decision": return fill(t(f.decision === "stands" ? "fVarStands" : "fVarOut", lang), v);
    default: return f.text;
  }
}

const MISSION: Record<string, Key> = { correct_calls: "mCorrect", underdog: "mUnderdog", stories: "mStories" };
export const missionLabel = (id: string, fallback: string, lang: Lang) => (MISSION[id] ? t(MISSION[id], lang) : fallback);
