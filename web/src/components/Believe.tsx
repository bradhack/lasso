import { t } from "../i18n";
import { useStore } from "../store";
import type { Lang, MatchSnapshot } from "../types";

const REWARD = 50;
const fmt = (n: number) => n.toLocaleString();

/**
 * Touch the sign. When a side falls behind, a taped-up BELIEVE sign goes up. Fans who still believe touch it
 * (your club if it's playing; otherwise whoever is behind). If that side draws level, every believer gets a
 * biscuit bonus and the sign turns gold.
 */
export function Believe({ snap, lang }: { snap: MatchSnapshot; lang: Lang }) {
  const user = useStore((s) => s.user);
  const believed = useStore((s) => s.believed);
  const touchSign = useStore((s) => s.touchSign);
  const mySide = user?.club_id === snap.home.club_id ? 0 : user?.club_id === snap.away.club_id ? 1 : null;
  const diff = snap.score[0] - snap.score[1];
  const trailing: 0 | 1 | null = diff === 0 ? null : diff > 0 ? 1 : 0;
  const side = mySide ?? trailing;
  const open = snap.status === "live" || snap.status === "half_time";
  const spell = side !== null && open ? snap.believe?.[side] ?? null : null;
  const won = snap.believe_won && (mySide === null || snap.believe_won.side === mySide) && snap.status !== "scheduled"
    ? snap.believe_won : null;

  if (spell && side !== null && user) {
    const team = side === 0 ? snap.home.name : snap.away.name;
    const touched = !!believed[`${snap.match_id}:${side}:${spell.spell}`];
    const touch = () => !touched && touchSign(snap.match_id, side);
    const sign = (
      <button className="sign" onClick={touch} disabled={touched} aria-pressed={touched}
        aria-label={t("believeIn", lang).replace("{team}", team)}>
        <i className="tape l" />
        <i className="tape r" />
        BELIEVE
      </button>
    );
    return (
      <section className={`believe card${touched ? " lit" : ""}`} aria-labelledby="believe-title">
        <div className="believe-top">
          {sign}
          <div className="believe-text">
            {/* A heading that says what to do; the sign itself is the only thing to tap. */}
            <h2 id="believe-title" className="eyebrow gold">{t("touchSign", lang)}</h2>
            {touched ? (
              <p className="believe-you">{t("believeYou", lang).replace("{n}", fmt(Math.max(0, spell.count - 1))).replace("{team}", team)}</p>
            ) : (
              <>
                <p className="believe-ask">{t("believeAsk", lang).replace("{team}", team).replace("{r}", String(REWARD))}</p>
                <span className="believe-count">{t("believeCount", lang).replace("{n}", fmt(spell.count))}</span>
              </>
            )}
          </div>
        </div>
      </section>
    );
  }

  if (won) {
    const team = won.side === 0 ? snap.home.name : snap.away.name;
    return (
      <section className="believe card won" role="status">
        <div className="believe-top">
          <div className="sign">
            <i className="tape l" />
            <i className="tape r" />
            BELIEVE
          </div>
          <p className="believe-you">{t("believeRight", lang).replace("{team}", team).replace("{n}", fmt(won.count))}</p>
        </div>
      </section>
    );
  }
  return null;
}
