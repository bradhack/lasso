import { useEffect, useMemo, useState } from "react";
import { t } from "../i18n";
import { useStore } from "../store";
import type { Lang, Market, MatchSnapshot } from "../types";
import { pct } from "./bits";

const STAKES = [50, 100, 250];

function minuteOf(period: number, clock: number) {
  return period === 1 ? clock : Math.max(clock, 45) + 0.0001;
}

export function CallIt({ snap, lang }: { snap: MatchSnapshot; lang: Lang }) {
  const calls = useStore((s) => s.calls);
  const user = useStore((s) => s.user);
  const placeCall = useStore((s) => s.placeCall);
  const [thrown, setThrown] = useState<string | null>(null);

  // Prefer an open market the fan has not called yet; otherwise show their latest locked call.
  const market: Market | undefined = useMemo(() => {
    const open = snap.markets.filter((m) => m.status === "open");
    return open.find((m) => !calls[m.market_id]) ?? open[open.length - 1] ??
      [...snap.markets].reverse().find((m) => calls[m.market_id] && m.status !== "settled");
  }, [snap.markets, calls]);

  const [pick, setPick] = useState<string | null>(null);
  const [stake, setStake] = useState(100);
  const [busy, setBusy] = useState(false);
  useEffect(() => setPick(null), [market?.market_id]);

  if (!market) {
    return (
      <section className="callit">
        <span className="eyebrow gold">{t("callIt", lang).toUpperCase()}</span>
        <div className="empty" style={{ paddingBottom: 6 }}>{snap.status === "finished" ? t("fullTime", lang) : t("waiting", lang)}</div>
      </section>
    );
  }

  const mine = calls[market.market_id];
  const chosen = market.options.find((o) => o.id === (mine?.option_id ?? pick)) ?? null;
  const yes = market.options.find((o) => o.id === "yes") ?? market.options[0];
  const now = minuteOf(snap.period, snap.clock);
  const closeAt = minuteOf(market.closes.period, market.closes.clock);
  const left = Math.max(0, closeAt - now);
  const open = market.status === "open" && left > 0;
  const payout = chosen ? Math.round(stake * chosen.multiplier) : 0;
  const cols = market.options.length === 3 ? "three" : "two";

  return (
    <section className={`callit${mine ? " locked" : ""}`}>
      <div className="row">
        <span className="eyebrow gold">{t("callIt", lang).toUpperCase()}</span>
        <span className="muted" style={{ fontSize: 12 }}>
          {open ? `${t("closes", lang)} ${Math.ceil(closeAt)}'` : t("closed", lang)}
        </span>
      </div>
      <h3>{market.question}</h3>
      <div className="muted" style={{ fontSize: 12 }}>
        {market.copy ?? `${t("gafferSays", lang)} ${pct(yes.p)}. ${t("beatIt", lang)}`}
      </div>
      <div className={`opts ${cols}`}>
        {market.options.map((o) => (
          <button
            key={o.id}
            className={`opt${chosen?.id === o.id ? " sel" : ""}`}
            disabled={!!mine || !open}
            onClick={() => setPick(o.id)}
            aria-pressed={chosen?.id === o.id}
          >
            <span style={{ fontSize: 13 }}>{o.label}</span>
            <span className="m">{o.multiplier.toFixed(1)}x</span>
          </button>
        ))}
      </div>
      {!mine && (
        <>
          <div className="stakes">
            <span className="muted" style={{ fontSize: 12, marginRight: 2 }}>{t("stake", lang)}</span>
            {STAKES.map((s) => (
              <button key={s} className={`stake${stake === s ? " sel" : ""}`} onClick={() => setStake(s)} aria-pressed={stake === s}
                disabled={!!user && user.biscuits < s}>
                {s}
              </button>
            ))}
          </div>
          <button
            className="cta"
            disabled={!chosen || !open || busy}
            onClick={async () => {
              if (!chosen) return;
              setBusy(true);
              await placeCall(market, chosen.id, stake);
              setBusy(false);
              setThrown(market.market_id);
            }}
          >
            {chosen ? `${t("lassoIt", lang)} · ${t("win", lang)} ${payout} ${t("biscuits", lang)}` : t("lassoIt", lang)}
          </button>
        </>
      )}
      {mine && (
        <div className="lasso-wrap">
          <div className="cta ghost locked">
            <span>{t("lockedIn", lang)} · {mine.label} · {mine.stake} → {Math.round(mine.stake * mine.multiplier)}</span>
          </div>
          {thrown === market?.market_id && <LassoThrow key={thrown} />}
        </div>
      )}
      {open && (
        <div className="timer" aria-hidden="true">
          <span style={{ width: `${Math.min(100, (left / 3) * 100)}%` }} />
        </div>
      )}
    </section>
  );
}

/**
 * The lasso: a rope flies in from the top right, its loop swings all the way around your call,
 * closes at the knot, then cinches tight.
 */
function LassoThrow() {
  // Loop: an ellipse around the button that starts at the knot and overshoots it slightly, so it visibly closes.
  const loop = "M372 22 A186 30 0 1 1 28 58 A186 30 0 1 1 380 27";
  const rope = "M430 -46 C418 -30 404 -10 388 8 C382 14 377 18 372 22";
  return (
    <svg className="lasso-throw" viewBox="0 0 400 80" preserveAspectRatio="none" aria-hidden="true">
      <g className="cinch">
        <path className="rope" pathLength={100} d={rope} />
        <path className="loop" pathLength={100} d={loop} />
        <ellipse className="knot" cx="373" cy="22" rx="5" ry="4" />
      </g>
    </svg>
  );
}
