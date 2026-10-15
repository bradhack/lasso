import { useEffect } from "react";
import { Crest } from "../components/bits";
import { LassoMark } from "../components/Icons";
import { Meter } from "../components/Meter";
import { loc } from "../i18n";
import { useStore } from "../store";
import type { Lang } from "../types";

/** Broadcast lower-third: transparent background, for OBS / vMix browser sources. */
export function Overlay({ id, lang }: { id: string; lang: Lang }) {
  const snap = useStore((s) => s.snapshots[id]);
  const watch = useStore((s) => s.watch);
  const connected = useStore((s) => s.connected);
  useEffect(() => {
    document.body.style.background = "transparent";
    document.documentElement.style.background = "transparent";
    watch(id).catch(() => undefined);
  }, [id, connected, watch]);
  if (!snap) return null;
  const moment = [...snap.moments].reverse().find((m) => m.trigger !== "kickoff");
  return (
    <div className="overlay-root">
      <div className="lower-third">
        <div className="row">
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <Crest club={snap.home} />
            <span className="score">{snap.score[0]}<span className="sep">:</span>{snap.score[1]}</span>
            <Crest club={snap.away} round />
            <span className="num" style={{ fontSize: 34, marginLeft: 8 }}>{snap.minute}'</span>
          </div>
          <span style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--gold)" }}>
            <LassoMark size={30} /><span style={{ fontFamily: "Sora", fontWeight: 700, fontSize: 24, color: "var(--text)" }}>lasso</span>
          </span>
        </div>
        <Meter snap={snap} lang={lang} compact />
        {moment && (
          <>
            <h3>{loc(moment.headline, lang)}</h3>
            <p>{loc(moment.story, lang)}</p>
          </>
        )}
      </div>
    </div>
  );
}
