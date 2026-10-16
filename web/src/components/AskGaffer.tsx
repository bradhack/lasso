import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api } from "../api";
import { t } from "../i18n";
import { useStore } from "../store";
import type { AskAnswer, Lang, MatchSnapshot } from "../types";
import { Sparkle } from "./Icons";
import { Listen } from "./Listen";
import { UnderTheHood } from "./UnderTheHood";

const NO_ASKS: AskAnswer[] = [];

/**
 * Ask the Gaffer: a fan types a question about the match; the Scout agent researches it with the Gaffer's
 * MCP tools and the Gaffer answers in the fan's language. Answers are private to the asker.
 */
export function AskGaffer({ snap, lang }: { snap: MatchSnapshot; lang: Lang }) {
  const user = useStore((s) => s.user);
  const items = useStore((s) => s.asks[snap.match_id] ?? NO_ASKS);
  const setAsks = useStore((s) => s.setAsks);
  const [q, setQ] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [all, setAll] = useState(false);
  const [hood, setHood] = useState<AskAnswer | null>(null);
  const busy = items.some((i) => i.pending);

  // The match loops in the demo: when it starts again, earlier answers no longer apply.
  const latest = Math.max(0, ...items.map((i) => i.minute));
  useEffect(() => {
    if (items.length && snap.minute < latest - 2) setAsks(snap.match_id, () => []);
  }, [snap.minute, latest]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!user) return null;

  const last = [...items].reverse().find((i) => !i.pending);
  const suggestions = last?.followups.length ? last.followups : [t("askS1", lang), t("askS4", lang), t("askS3", lang)];
  const shown = all ? items : items.slice(-2);

  async function send(text: string) {
    const question = text.trim();
    if (!user || question.length < 3 || busy) return;
    const tmp = `tmp-${Date.now()}`;
    const draft: AskAnswer = { ask_id: tmp, question, answer: "", followups: [], source: "gaffer", trace: [],
      minute: snap.minute, latency_ms: 0, pending: true };
    setAsks(snap.match_id, (l) => [...l, draft]);
    setQ("");
    setNote(null);
    try {
      const r = await api.ask(snap.match_id, { user_id: user.id, question, lang });
      setAsks(snap.match_id, (l) => l.map((x) => (x.ask_id === tmp ? r : x)).slice(-20));
    } catch (e) {
      setAsks(snap.match_id, (l) => l.filter((x) => x.ask_id !== tmp));
      const m = (e as Error).message;
      setNote(t(m === "slow_down" ? "askSlow" : m === "daily_limit" ? "askLimit" : m === "busy" ? "askBusy" : "askFail", lang));
      setQ(question);
    }
  }

  const submit = (e: FormEvent) => {
    e.preventDefault();
    send(q);
  };

  return (
    <section className="card ask" aria-label={t("askTitle", lang)}>
      <div className="row">
        <span className="eyebrow gold">{t("askTitle", lang)}</span>
        {items.length > 2 && (
          <button className="linkbtn" onClick={() => setAll(!all)}>{all ? t("showLess", lang) : `${t("showAll", lang)} (${items.length})`}</button>
        )}
      </div>
      {items.length === 0 && <p className="ask-sub">{t("askSub", lang)}</p>}
      {shown.length > 0 && (
        <div className="thread" aria-live="polite">
          {shown.map((i) => (
            <div key={i.ask_id} className="qa">
              <div className="bubble me"><span className="who">{t("you", lang)} · {i.minute}'</span>{i.question}</div>
              {i.pending ? (
                <div className="bubble gaffer thinking"><span className="who">Gaffer</span>{t("askThinking", lang)}<span className="dots"><i /><i /><i /></span></div>
              ) : (
                <div className="bubble gaffer">
                  <span className="who">Gaffer</span>
                  {i.answer}
                  <span className="bubble-actions">
                    <Listen kind="answer" id={i.ask_id} text={i.answer} lang={lang} />
                    {i.source === "agents" && i.trace.length > 0 && (
                      <button className="by" onClick={() => setHood(i)} aria-label={t("uth", lang)}>
                        <Sparkle size={11} /> {t("askBy", lang).replace("{n}", String(i.trace.length)).replace("{s}", (i.latency_ms / 1000).toFixed(1))} <span className="chev">›</span>
                      </button>
                    )}
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      <div className="ask-chips">
        {suggestions.map((s) => (
          <button key={s} className="ask-chip" disabled={busy} onClick={() => send(s)}>{s}</button>
        ))}
      </div>
      <form className="ask-form" onSubmit={submit}>
        <input value={q} onChange={(e) => setQ(e.target.value)} maxLength={200} placeholder={t("askPlaceholder", lang)}
          aria-label={t("askPlaceholder", lang)} enterKeyHint="send" disabled={busy} />
        <button className="cta" type="submit" disabled={busy || q.trim().length < 3}>{t("askSend", lang)}</button>
      </form>
      {note && <p className="ask-note" role="status">{note}</p>}
      {hood && <UnderTheHood kind="answer" trace={hood.trace} latencyMs={hood.latency_ms} onClose={() => setHood(null)} />}
    </section>
  );
}
