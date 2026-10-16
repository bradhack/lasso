import { useEffect, useState } from "react";
import { t } from "../i18n";
import { useStore } from "../store";
import type { Lang, MatchSnapshot } from "../types";
import { reasonText } from "../words";
import { EventIcon } from "./EventIcon";

const SHOW_MS = 4500;

/** A goal or a VAR decision, announced over the page for a few seconds as it happens (it's in the match
 * story too). Tap to dismiss. */
export function MatchBanner({ snap, lang }: { snap: MatchSnapshot; lang: Lang }) {
  const flash = useStore((s) => s.flash);
  const [gone, setGone] = useState<number | null>(null);
  const mine = flash && flash.match_id === snap.match_id ? flash : null;
  const live = !!mine && Date.now() - mine.at < SHOW_MS && gone !== mine.at;
  const [, tick] = useState(0);
  useEffect(() => {
    if (!live || !mine) return;
    const tm = window.setTimeout(() => tick((n) => n + 1), SHOW_MS - (Date.now() - mine.at) + 30);
    return () => window.clearTimeout(tm);
  }, [mine?.at, live]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!live || !mine) return null;
  const club = mine.team === 0 ? snap.home : snap.away;
  const goal = mine.kind === "goal";
  const title = goal ? t("bnGoal", lang) : mine.kind === "var_stands" ? t("varStands", lang)
    : t("varRuledOut", lang).replace("{reason}", reasonText(mine.reason, lang));
  const score = mine.score ?? snap.score;
  return (
    <div className={`match-banner ${mine.kind}`} role="status" aria-live="assertive" onClick={() => setGone(mine.at)}
      style={{ ["--team" as string]: mine.team === 0 ? "var(--home)" : "var(--away)" }}>
      <EventIcon kind={goal ? "goal" : "var"} size={26} />
      <div className="mb-text">
        <b>{title}</b>
        <span>{mine.player} · {club.name} · {mine.minute}'{goal ? ` · ${snap.home.short} ${score[0]}-${score[1]} ${snap.away.short}` : ""}</span>
      </div>
    </div>
  );
}
