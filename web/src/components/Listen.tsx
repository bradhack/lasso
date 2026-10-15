import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { HTML_LANG, t } from "../i18n";
import { useStore } from "../store";
import type { Lang } from "../types";
import { Speaker, StopIcon } from "./Icons";

/** A story's headline and text as one passage, with a pause between them (as the server reads it). */
export function storyText(headline: string, story: string) {
  const h = headline.trim();
  return `${h && !/[.!?]$/.test(h) ? `${h}.` : h} ${story}`.trim();
}

// Only one thing speaks at a time: starting a new one stops the last.
let current: { key: string; stop: () => void } | null = null;

/**
 * Listen: reads a story or a Gaffer answer aloud. Uses Azure AI Speech neural voices when the server has it,
 * otherwise the phone's own voice. Playback starts inside the tap, which iPhones require.
 */
export function Listen({ kind, id, matchId, text, lang, compact = false }: {
  kind: "story" | "answer"; id: string; matchId?: string; text: string; lang: Lang; compact?: boolean;
}) {
  const azure = useStore((s) => s.speechAzure);
  const [state, setState] = useState<"idle" | "loading" | "playing">("idle");
  const key = `${kind}:${id}:${lang}`;
  const mounted = useRef(true);
  useEffect(() => () => {
    mounted.current = false;
    if (current?.key === key) current.stop();
  }, [key]);

  const done = () => {
    if (current?.key === key) current = null;
    if (mounted.current) setState("idle");
  };

  const phoneVoice = () => {
    if (!("speechSynthesis" in window)) return done();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = HTML_LANG[lang];
    u.rate = 0.98;
    u.onend = done;
    u.onerror = done;
    current = { key, stop: () => { speechSynthesis.cancel(); done(); } };
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
    setState("playing");
  };

  const toggle = () => {
    if (state !== "idle") {
      current?.stop();
      return;
    }
    current?.stop();
    if (!azure) return phoneVoice();
    const audio = new Audio(api.speechUrl({ kind, id, lang, match_id: matchId }));
    current = { key, stop: () => { audio.pause(); done(); } };
    audio.onplaying = () => mounted.current && setState("playing");
    audio.onended = done;
    audio.onerror = () => {
      // Azure Speech unavailable for this one: fall back to the phone's voice where the browser allows it.
      done();
      phoneVoice();
    };
    setState("loading");
    audio.play().catch(() => undefined);
  };

  const playing = state === "playing";
  return (
    <button className={`listen ${state}${compact ? " compact" : ""}`} onClick={toggle}
      aria-label={playing ? t("stopListen", lang) : t("listenAria", lang)} aria-pressed={playing}>
      {playing ? <StopIcon size={compact ? 11 : 13} /> : <Speaker size={compact ? 12 : 14} />}
      {!compact && <span>{playing ? t("stopListen", lang) : t("listen", lang)}</span>}
    </button>
  );
}
