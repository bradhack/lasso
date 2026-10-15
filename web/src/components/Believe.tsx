import { useEffect, useRef, useState } from "react";
import { t } from "../i18n";
import { useStore } from "../store";
import type { Lang, MatchSnapshot } from "../types";

/**
 * A taped-up BELIEVE sign. It goes up when your club falls behind, or when you back a comeback,
 * and stays up (gold) if they come back.
 */
export function Believe({ snap, lang }: { snap: MatchSnapshot; lang: Lang }) {
  const user = useStore((s) => s.user);
  const calls = useStore((s) => s.calls);
  const side = user?.club_id === snap.home.club_id ? 0 : user?.club_id === snap.away.club_id ? 1 : null;
  const backedComeback = Object.values(calls).some(
    (c) => c.market_id.startsWith(`${snap.match_id}:comeback`) && c.option_id === "yes",
  );
  const diff = snap.score[0] - snap.score[1];
  const trailingSide = diff === 0 ? null : diff > 0 ? 1 : 0;
  const myBehind = side !== null && trailingSide === side;
  const believing = snap.status !== "scheduled" && (myBehind || (backedComeback && trailingSide !== null));

  // Remember who we were believing in, so we can celebrate when they draw level or go ahead.
  const believedIn = useRef<number | null>(null);
  const [cameBack, setCameBack] = useState(false);
  useEffect(() => {
    if (believing && trailingSide !== null) believedIn.current = trailingSide;
    const who = believedIn.current;
    if (who !== null && !believing) {
      const mine = who === 0 ? snap.score[0] : snap.score[1];
      const theirs = who === 0 ? snap.score[1] : snap.score[0];
      if (mine >= theirs) setCameBack(true);
    }
  }, [believing, trailingSide, snap.score[0], snap.score[1]]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    // A new replay of the match starts fresh.
    if (snap.score[0] === 0 && snap.score[1] === 0 && snap.minute < 2) {
      believedIn.current = null;
      setCameBack(false);
    }
  }, [snap.score, snap.minute]);

  if (!believing && !cameBack) return null;
  const team = believedIn.current === 1 ? snap.away.name : believedIn.current === 0 ? snap.home.name : "";
  const caption = cameBack
    ? t("cameBack", lang).replace("{team}", team)
    : myBehind
      ? t("behind", lang).replace("{team}", side === 0 ? snap.home.name : snap.away.name)
      : t("backedIt", lang);
  return (
    <div className={`believe${cameBack ? " won" : ""}`} role="status">
      <div className="sign" aria-label="Believe">
        <i className="tape l" />
        <i className="tape r" />
        BELIEVE
      </div>
      <span>{caption}</span>
    </div>
  );
}
