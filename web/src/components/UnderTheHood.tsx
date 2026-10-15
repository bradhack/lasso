import { createPortal } from "react-dom";
import { t } from "../i18n";
import { useStore } from "../store";
import type { AgentTrace, Lang } from "../types";
import { useDialog } from "../useDialog";

/** Each agent's name and job, in the fan's language. */
const AGENTS: Record<string, Record<Lang, [string, string]>> = {
  stats: { en: ["Stats agent", "Pulls the numbers that matter"], es: ["Agente de estadísticas", "Saca los números que importan"], pt: ["Agente de estatísticas", "Busca os números que importam"], fr: ["Agent stats", "Sort les chiffres qui comptent"] },
  gaffer: { en: ["Gaffer agent", "Explains why the chances moved"], es: ["Agente Gaffer", "Explica por qué cambiaron las opciones"], pt: ["Agente Gaffer", "Explica por que as chances mudaram"], fr: ["Agent Gaffer", "Explique pourquoi les chances ont bougé"] },
  narrator: { en: ["Narrator", "Writes the story in four languages"], es: ["Narrador", "Escribe la historia en cuatro idiomas"], pt: ["Narrador", "Escreve a história em quatro idiomas"], fr: ["Narrateur", "Écrit le récit en quatre langues"] },
  persona: { en: ["Persona", "Writes the fan and analyst angles"], es: ["Persona", "Escribe los enfoques para aficionados y analistas"], pt: ["Persona", "Escreve os ângulos para torcedores e analistas"], fr: ["Persona", "Écrit les angles supporter et analyste"] },
  game_master: { en: ["Game Master", "Picks the next Call It challenge"], es: ["Game Master", "Elige el próximo reto"], pt: ["Game Master", "Escolhe o próximo desafio"], fr: ["Game Master", "Choisit le prochain défi"] },
  scout: { en: ["Scout", "Picks the data tools for your question"], es: ["Ojeador", "Elige las herramientas de datos para tu pregunta"], pt: ["Olheiro", "Escolhe as ferramentas de dados para sua pergunta"], fr: ["Recruteur", "Choisit les outils de données pour ta question"] },
  presser: { en: ["The Gaffer", "Answers in your language, from the Scout's notes"], es: ["El Gaffer", "Responde en tu idioma con las notas del ojeador"], pt: ["O Gaffer", "Responde no seu idioma com as notas do olheiro"], fr: ["Le Gaffer", "Répond dans ta langue avec les notes du recruteur"] },
};

const secs = (ms: number) => `${(ms / 1000).toFixed(1)}s`;
const argText = (args?: Record<string, unknown>) =>
  args && Object.keys(args).length ? `(${Object.entries(args).map(([k, v]) => `${k}: ${String(v)}`).join(", ")})` : "";

/** Where each agent's bar sits on the timeline: from recorded start times, or round by round for older traces. */
function layout(trace: AgentTrace[]) {
  if (trace.every((a) => typeof a.start === "number")) {
    const t0 = Math.min(...trace.map((a) => a.start!));
    return trace.map((a) => ({ a, from: (a.start! - t0) * 1000 }));
  }
  const roundEnd: Record<number, number> = {};
  return trace.map((a) => {
    const stage = a.stage ?? 1;
    const from = Object.entries(roundEnd).filter(([s]) => Number(s) < stage).reduce((m, [, v]) => Math.max(m, v), 0);
    roundEnd[stage] = Math.max(roundEnd[stage] ?? 0, from + a.ms);
    return { a, from };
  });
}

export function UnderTheHood({ kind, trace, latencyMs, onClose }: {
  kind: "story" | "answer"; trace: AgentTrace[]; latencyMs?: number; onClose: () => void;
}) {
  const lang = useStore((s) => s.lang);
  const panel = useDialog<HTMLDivElement>(onClose);
  const rows = layout(trace);
  const span = Math.max(1, ...rows.map((r) => r.from + r.a.ms));
  const stages = [...new Set(trace.map((a) => a.stage ?? 1))].sort();
  const tokens = trace.reduce((n, a) => n + (a.in ?? 0) + (a.out ?? 0), 0);
  const models = [...new Set(trace.map((a) => a.model).filter(Boolean))];
  const path = ["Lasso API", "A2A", kind === "story" ? "Match Director" : "Press Room", "MCP", "Microsoft Foundry"];

  return createPortal(
    <div className="sheet" role="dialog" aria-modal="true" aria-labelledby="uth-title" onClick={onClose}>
      <div className="sheet-inner uth" ref={panel} tabIndex={-1} onClick={(e) => e.stopPropagation()}>
        <h2 id="uth-title" className="num" style={{ margin: 0, fontSize: 30 }}>{t("uth", lang).toUpperCase()}</h2>
        <p className="muted" style={{ margin: 0, lineHeight: 1.5 }}>
          {t(kind === "story" ? "uthStory" : "uthAnswer", lang).replace("{n}", String(trace.length))}
        </p>
        <div className="uth-path" aria-label="Request path">
          {path.map((p, i) => (
            <span key={p}>{i > 0 && <i>→</i>}<b>{p}</b></span>
          ))}
        </div>
        {stages.map((st) => {
          const inStage = rows.filter((r) => (r.a.stage ?? 1) === st);
          return (
            <div key={st} className="uth-stage">
              <div className="eyebrow">
                {t("uthRound", lang).replace("{n}", String(st))}
                {inStage.length > 1 && ` · ${t("uthParallel", lang).replace("{n}", String(inStage.length))}`}
              </div>
              {inStage.map(({ a, from }) => {
                const [name, role] = AGENTS[a.agent]?.[lang] ?? [a.agent, ""];
                return (
                  <div key={a.agent} className={`uth-agent${a.ok ? "" : " failed"}`}>
                    <div className="row">
                      <b>{name}</b>
                      <span className="uth-ms">{secs(a.ms)}</span>
                    </div>
                    <span className="uth-role">{a.ok ? role : t("uthFailed", lang)}</span>
                    <div className="uth-bar" aria-hidden="true">
                      <span style={{ left: `${(from / span) * 100}%`, width: `${Math.max(2, (a.ms / span) * 100)}%` }} />
                    </div>
                    <div className="uth-tools">
                      {a.tools?.length
                        ? a.tools.map((tl, i) => <code key={i}>{tl.name}{argText(tl.args)}</code>)
                        : <span className="muted">{t("uthNoTools", lang)}</span>}
                    </div>
                    {(a.in || a.out) ? (
                      <span className="uth-meta">{(a.in ?? 0).toLocaleString()} in · {(a.out ?? 0).toLocaleString()} out{a.model ? ` · ${a.model}` : ""}</span>
                    ) : a.model ? <span className="uth-meta">{a.model}</span> : null}
                  </div>
                );
              })}
            </div>
          );
        })}
        <div className="uth-total">
          <span>{t("uthTotal", lang)}</span>
          <b>{secs(latencyMs ?? span)}</b>
          {tokens > 0 && <span>{tokens.toLocaleString()} tokens</span>}
          {models.length > 0 && <span>{models.join(", ")}</span>}
        </div>
        <p className="uth-note">{t("uthNote", lang)}</p>
        <button className="cta" onClick={onClose}>{t("gotIt", lang)}</button>
      </div>
    </div>,
    document.body,
  );
}
