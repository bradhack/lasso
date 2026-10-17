import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { t } from "../i18n";
import { useStore } from "../store";
import type { Lang } from "../types";
import { Speaker, StopIcon } from "./Icons";

/** A story's headline and text as one passage, with a pause between them (as the server reads it). */
export function storyText(headline: string, story: string) {
  const h = headline.trim();
  return `${h && !/[.!?]$/.test(h) ? `${h}.` : h} ${story}`.trim();
}

// Without a server voice list, the phone reads English with a British accent too.
const DEFAULT_LOCALE: Record<Lang, string> = { en: "en-GB", es: "es-ES", pt: "pt-BR", fr: "fr-FR" };
const VS: Record<Lang, string> = { en: "versus", es: "contra", pt: "contra", fr: "contre" };
const TO: Record<Lang, string> = { en: "to", es: "a", pt: "a", fr: "à" };
const PLUS: Record<Lang, string> = { en: "plus", es: "más", pt: "mais", fr: "plus" };
const XG: Record<Lang, string> = { en: "expected goals", es: "goles esperados", pt: "gols esperados", fr: "buts attendus" };
const PTS: Record<Lang, string> = { en: "points", es: "puntos", pt: "pontos", fr: "points" };
const ord = (n: number) => `${n}${n % 100 >= 10 && n % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th"}`;

/** Text as a voice should read it (same rules as the server): 82' becomes "the 82nd minute", "v" becomes
 * "versus", 2-1 reads "2 to 1", and abbreviations are spelled out. */
export function spoken(text: string, lang: Lang) {
  return text
    .replace(/(?:\b(at|in|aos|à|a)\s+)?\b(\d{1,3})(?:\s*\+\s*(\d{1,2}))?['’′]/g, (_m, prep: string | undefined, num: string, extra: string | undefined) => {
      const n = Number(num);
      const plus = extra ? ` ${PLUS[lang]} ${extra}` : "";
      if (lang === "en") return prep ? `in the ${ord(n)} minute${plus}` : `${ord(n)} minute${plus}`;
      if (lang === "pt") return prep === "aos" ? `aos ${n}${plus} minutos` : `minuto ${n}${plus}`;
      if (lang === "fr") return prep === "à" ? `à la ${n}e minute${plus}` : `${n}e minute${plus}`;
      return `${prep ? `${prep} ` : ""}minuto ${n}${plus}`;
    })
    .replace(/(\w) v\.? (?=\w)/g, `$1 ${VS[lang]} `)
    .replace(/\b(\d{1,2})\s*-\s*(\d{1,2})\b(?!\s*%)/g, (_m, a: string, b: string) => `${a} ${TO[lang]} ${b}`)
    .replace(/\bxG\b/g, XG[lang])
    .replace(/\bpts\b/g, PTS[lang])
    .replace(/→/g, ` ${TO[lang]} `);
}

// All Ears: tell the server the first time this fan listens (once per visit is plenty).
let told = false;
function tellListened(matchId?: string) {
  const u = useStore.getState().user;
  if (told || !u || !matchId) return;
  told = true;
  api.listened(matchId, { user_id: u.id }).catch(() => { told = false; });
}

// Only one thing speaks at a time: starting a new one stops the last.
let current: { key: string; stop: () => void } | null = null;

/**
 * Listen: reads a story, a match event or a Gaffer answer aloud. Uses Azure AI Speech neural voices when the server has it,
 * otherwise the phone's own voice. Playback starts inside the tap, which iPhones require.
 */
export function Listen({ kind, id, matchId, text, lang, compact = false, label }: {
  kind: "story" | "answer" | "event" | "sample"; id: string; matchId?: string; text: string; lang: Lang; compact?: boolean;
  /** What this button reads, for screen readers when many Listen buttons sit in one list. */
  label?: string;
}) {
  const azure = useStore((s) => s.speechAzure);
  const options = useStore((s) => s.voices[lang]);
  const picked = useStore((s) => s.voicePick[lang]);
  // The fan's voice for this language if it's still offered; otherwise the default (British for English).
  const voice = options?.find((v) => v.id === picked)?.id ?? options?.[0]?.id;
  const [state, setState] = useState<"idle" | "loading" | "playing">("idle");
  const key = `${kind}:${id}:${lang}:${voice ?? ""}`;
  const mounted = useRef(true);
  // A new story in the same place (Why it moved shows the latest one) is a fresh button: stop what this one was
  // reading and start idle. Without this, the button stayed stuck on "loading" and every tap after was a "stop".
  useEffect(() => {
    mounted.current = true;
    setState("idle");
    return () => {
      mounted.current = false;
      if (current?.key === key) current.stop();
    };
  }, [key]);

  const done = () => {
    if (current?.key === key) current = null;
    if (mounted.current) setState("idle");
  };

  const phoneVoice = () => {
    if (!("speechSynthesis" in window)) return done();
    const u = new SpeechSynthesisUtterance(spoken(text, lang));
    // The phone's own voices: one with the chosen accent if it has one ("en-GB-RyanNeural" -> en-GB).
    const locale = voice ? voice.split("-").slice(0, 2).join("-") : DEFAULT_LOCALE[lang];
    u.lang = locale;
    const local = speechSynthesis.getVoices().find((v) => v.lang.replace("_", "-") === locale);
    if (local) u.voice = local;
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
    tellListened(matchId);
    if (!azure) return phoneVoice();
    const audio = new Audio(api.speechUrl({ kind, id, lang, match_id: matchId, voice }));
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
      aria-label={`${playing ? t("stopListen", lang) : t("listenAria", lang)}${label ? `: ${label}` : ""}`} aria-pressed={playing}>
      {playing ? <StopIcon size={compact ? 11 : 13} /> : <Speaker size={compact ? 12 : 14} />}
      {!compact && <span>{playing ? t("stopListen", lang) : t("listen", lang)}</span>}
    </button>
  );
}
