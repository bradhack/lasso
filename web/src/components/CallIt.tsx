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
            }}
          >
            {chosen ? `${t("lassoIt", lang)} · ${t("win", lang)} ${payout} ${t("biscuits", lang)}` : t("lassoIt", lang)}
          </button>
        </>
      )}
      {mine && (
        <div className="cta ghost" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
          {t("lockedIn", lang)} · {mine.label} · {mine.stake} → {Math.round(mine.stake * mine.multiplier)}
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
