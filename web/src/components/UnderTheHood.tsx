import { createPortal } from "react-dom";
import { t } from "../i18n";
import { useStore } from "../store";
import type { AgentTrace, Lang } from "../types";
import { useDialog } from "../useDialog";

/** Each agent's name and job, in the fan's language. */
const AGENTS: Record<string, Record<Lang, [string, string]>> = {
  stats: { en: ["Stats agent", "Pulls the numbers that matter"], es: ["Agente de estadísticas", "Saca los números que importan"], pt: ["Agente de estatísticas", "Busca os números que importam"], fr: ["Agent stats", "Sort les chiffres qui comptent"] },
  gaffer: { en: ["Gaffer agent", "Explains what changed the win probability"], es: ["Agente Gaffer", "Explica qué cambió la probabilidad de victoria"], pt: ["Agente Gaffer", "Explica o que mudou a probabilidade de vitória"], fr: ["Agent Gaffer", "Explique ce qui a changé la probabilité de victoire"] },
  narrator: { en: ["Narrator", "Writes the story in four languages"], es: ["Narrador", "Escribe la historia en cuatro idiomas"], pt: ["Narrador", "Escreve a história em quatro idiomas"], fr: ["Narrateur", "Écrit le récit en quatre langues"] },
  persona: { en: ["Persona", "Writes the fan and analyst angles"], es: ["Persona", "Escribe los enfoques para aficionados y analistas"], pt: ["Persona", "Escreve os ângulos para torcedores e analistas"], fr: ["Persona", "Écrit les angles supporter et analyste"] },
  game_master: { en: ["Game Master", "Picks the next Call It challenge"], es: ["Game Master", "Elige el próximo reto"], pt: ["Game Master", "Escolhe o próximo desafio"], fr: ["Game Master", "Choisit le prochain défi"] },
  scout: { en: ["Scout", "Picks the data tools for your question"], es: ["Ojeador", "Elige las herramientas de datos para tu pregunta"], pt: ["Olheiro", "Escolhe as ferramentas de dados para sua pergunta"], fr: ["Recruteur", "Choisit les outils de données pour ta question"] },
  presser: { en: ["The Gaffer", "Answers in your language, from the Scout's notes"], es: ["El Gaffer", "Responde en tu idioma con las notas del ojeador"], pt: ["O Gaffer", "Responde no seu idioma com as notas do olheiro"], fr: ["Le Gaffer", "Répond dans ta langue avec les notes du recruteur"] },
};

type L = Record<Lang, string>;

/** How a run recovered (or why it stopped), in the fan's language. */
const RECOVERY: Record<string, L> = {
  scoutTimeout: { en: "Ran out of time, so the Gaffer answered from the match facts it always gets", es: "Se quedó sin tiempo, así que el Gaffer respondió con los datos del partido que siempre recibe", pt: "Ficou sem tempo, então o Gaffer respondeu com os dados da partida que sempre recebe", fr: "À court de temps : le Gaffer a répondu avec les faits du match qu'il reçoit toujours" },
  superseded: { en: "Was slow, so a second try ran alongside it and finished first", es: "Iba lento, así que un segundo intento corrió a la vez y terminó antes", pt: "Estava lento, então uma segunda tentativa rodou junto e terminou antes", fr: "Trop lent : un second essai a tourné en parallèle et a fini avant" },
  hedge: { en: "The second try, started because the first was slow, answered first", es: "El segundo intento, lanzado porque el primero iba lento, respondió antes", pt: "A segunda tentativa, iniciada porque a primeira estava lenta, respondeu antes", fr: "Le second essai, lancé car le premier traînait, a répondu en premier" },
  retry: { en: "Its first reply was unusable, so it was asked once more", es: "Su primera respuesta no servía, así que se le pidió otra vez", pt: "A primeira resposta não servia, então foi pedida de novo", fr: "Sa première réponse était inutilisable : on lui a redemandé" },
  recovered: { en: "Its reply was malformed; the answer was recovered from it", es: "Su respuesta llegó mal formada; se recuperó la respuesta", pt: "A resposta veio malformada; o texto foi recuperado", fr: "Sa réponse était mal formée ; le texte a été récupéré" },
  answerFailed: { en: "Didn't finish in time", es: "No terminó a tiempo", pt: "Não terminou a tempo", fr: "Pas fini à temps" },
};

const KEPT_STORY: L = { en: "Kept the instant story: ", es: "Se quedó la historia instantánea: ", pt: "Ficou a história instantânea: ", fr: "Récit instantané conservé : " };
const KEPT_HEAD: L = { en: "Kept the instant headline: ", es: "Se quedó el titular instantáneo: ", pt: "Ficou a manchete instantânea: ", fr: "Titre instantané conservé : " };

/** What each code check fixed, in the fan's language. */
const FIXES: Record<string, L> = {
  wording: { en: "Tidied the wording (spelling, numbers, translation)", es: "Pulió la redacción (ortografía, números, traducción)", pt: "Ajustou o texto (ortografia, números, tradução)", fr: "A retouché la formulation (orthographe, chiffres, traduction)" },
  real_clubs: { en: "Removed a real club's name", es: "Quitó el nombre de un club real", pt: "Removeu o nome de um clube real", fr: "A retiré le nom d'un vrai club" },
  xg_for_fans: { en: "Took out expected-goals decimals for a fan", es: "Quitó los decimales de goles esperados para un aficionado", pt: "Tirou os decimais de gols esperados para um torcedor", fr: "A retiré les décimales de buts attendus pour un supporter" },
  final_chances: { en: "Removed a chance quoted after full time", es: "Quitó una probabilidad citada tras el final", pt: "Removeu uma chance citada depois do apito final", fr: "A retiré une probabilité citée après le coup de sifflet final" },
  wrong_team_pct: { en: "Removed a percentage given to the wrong club", es: "Quitó un porcentaje atribuido al club equivocado", pt: "Removeu uma porcentagem dada ao clube errado", fr: "A retiré un pourcentage attribué au mauvais club" },
  wrong_leader: { en: "Removed a sentence with the wrong club in front", es: "Quitó una frase que ponía por delante al club equivocado", pt: "Removeu uma frase com o clube errado na frente", fr: "A retiré une phrase qui mettait le mauvais club devant" },
  trailing_question: { en: "Cut a question at the end (suggestions go below)", es: "Quitó una pregunta al final (las sugerencias van debajo)", pt: "Cortou uma pergunta no final (as sugestões ficam abaixo)", fr: "A coupé une question finale (les suggestions sont en dessous)" },
  sources: { en: "Removed talk about notes or tools", es: "Quitó una mención a notas o herramientas", pt: "Removeu uma menção a notas ou ferramentas", fr: "A retiré une mention de notes ou d'outils" },
  next_goal_side: { en: "Removed the wrong club as likelier to score next", es: "Quitó al club equivocado como más probable para marcar el siguiente gol", pt: "Removeu o clube errado como mais provável de marcar o próximo gol", fr: "A retiré le mauvais club comme plus susceptible de marquer le prochain but" },
  shots: { en: "Removed a wrong claim about shots", es: "Quitó un dato erróneo sobre los tiros", pt: "Removeu uma informação errada sobre os chutes", fr: "A retiré une affirmation fausse sur les tirs" },
  guessed_tactic: { en: "Cut a guess about tactics Lasso doesn't track", es: "Quitó una suposición sobre tácticas que Lasso no sigue", pt: "Cortou um palpite sobre táticas que o Lasso não acompanha", fr: "A coupé une supposition sur une tactique que Lasso ne suit pas" },
  certainty: { en: "Changed 0% or 100% to under 1% or over 99%: nothing is certain yet", es: "Cambió 0% o 100% por menos del 1% o más del 99%: aún no hay nada seguro", pt: "Trocou 0% ou 100% por menos de 1% ou mais de 99%: ainda nada é certo", fr: "A changé 0 % ou 100 % en moins de 1 % ou plus de 99 % : rien n'est encore joué" },
  neutral: { en: "Removed a sentence that took a side", es: "Quitó una frase que tomaba partido", pt: "Removeu uma frase que tomava partido", fr: "A retiré une phrase qui prenait parti" },
  full_names: { en: "Gave a player his full name", es: "Puso el nombre completo de un jugador", pt: "Colocou o nome completo de um jogador", fr: "A mis le nom complet d'un joueur" },
  next_goal_order: { en: "Put the club likelier to score next first", es: "Puso primero al club más probable para marcar", pt: "Colocou primeiro o clube mais provável de marcar", fr: "A mis en premier le club le plus susceptible de marquer" },
  rise: { en: "Fixed a rise that didn't add up", es: "Corrigió una subida que no cuadraba", pt: "Corrigiu uma subida que não batia", fr: "A corrigé une hausse qui ne collait pas" },
  season_words: { en: "Fixed match chances called season chances", es: "Corrigió probabilidades del partido llamadas de la temporada", pt: "Corrigiu chances da partida chamadas de chances da temporada", fr: "A corrigé des chances du match présentées comme celles de la saison" },
  length: { en: "Trimmed it to length", es: "La recortó a su longitud", pt: "Encurtou para o tamanho certo", fr: "L'a raccourcie à la bonne longueur" },
  // Stories: the instant (template) version stays when the agents' version gets a fact or a tone wrong.
  story_red_filler: { en: "the agents brought up the red card when it wasn't the story", es: "los agentes sacaron la roja sin que fuera la noticia", pt: "os agentes citaram o vermelho sem que fosse a notícia", fr: "les agents parlaient du rouge alors que ce n'était pas le sujet" },
  story_draw: { en: "it didn't give the draw's chance, from and to", es: "no daba la probabilidad del empate, de cuánto a cuánto", pt: "não dava a chance de empate, de quanto para quanto", fr: "il ne donnait pas les chances du nul, avant et après" },
  story_stiff: { en: "it used a forced phrase", es: "usaba una expresión forzada", pt: "usava uma expressão forçada", fr: "il employait une tournure forcée" },
  story_time: { en: "its time left wasn't to halftime", es: "el tiempo restante no era hasta el descanso", pt: "o tempo restante não era até o intervalo", fr: "le temps restant n'était pas celui avant la mi-temps" },
  story_goal_minute: { en: "a goal's minute was wrong", es: "el minuto de un gol estaba mal", pt: "o minuto de um gol estava errado", fr: "la minute d'un but était fausse" },
  story_leader: { en: "it had the wrong club in front", es: "ponía por delante al club equivocado", pt: "colocava o clube errado na frente", fr: "il mettait le mauvais club devant" },
  story_player: { en: "it didn't name the player", es: "no nombraba al jugador", pt: "não citava o jogador", fr: "il ne nommait pas le joueur" },
  story_var: { en: "it didn't say what the ruled-out goal would have meant", es: "no decía qué habría supuesto el gol anulado", pt: "não dizia o que o gol anulado teria significado", fr: "il ne disait pas ce qu'aurait changé le but refusé" },
  headline_favors: { en: "it cheered a club whose chance fell", es: "animaba a un club cuya probabilidad bajó", pt: "exaltava um clube cuja chance caiu", fr: "il saluait un club dont les chances baissaient" },
  headline_time: { en: "its time left wasn't to halftime", es: "el tiempo restante no era hasta el descanso", pt: "o tempo restante não era até o intervalo", fr: "le temps restant n'était pas celui avant la mi-temps" },
};

function fixText(code: string, lang: Lang): string {
  const label = FIXES[code]?.[lang] ?? code;
  if (code.startsWith("story_")) return KEPT_STORY[lang] + label;
  if (code.startsWith("headline_")) return KEPT_HEAD[lang] + label;
  return label;
}

function recoveryNote(a: AgentTrace, kind: "story" | "answer", lang: Lang): string | null {
  if (a.error === "Superseded") return RECOVERY.superseded[lang];
  if (!a.ok) return kind === "story" ? t("uthFailed", lang) : a.agent === "scout" ? RECOVERY.scoutTimeout[lang] : RECOVERY.answerFailed[lang];
  if (a.hedge) return RECOVERY.hedge[lang];
  if (a.retry) return RECOVERY.retry[lang];
  if (a.recovered) return RECOVERY.recovered[lang];
  return null;
}

/** How many different agents took part (the code checks aren't an agent; a retried agent counts once). */
export const agentCount = (trace: AgentTrace[]) => new Set(trace.filter((a) => a.agent !== "checks").map((a) => a.agent)).size;

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

export function UnderTheHood({ kind, trace: fullTrace, latencyMs, onClose }: {
  kind: "story" | "answer"; trace: AgentTrace[]; latencyMs?: number; onClose: () => void;
}) {
  const lang = useStore((s) => s.lang);
  const panel = useDialog<HTMLDivElement>(onClose);
  const checks = fullTrace.find((a) => a.agent === "checks");
  const trace = fullTrace.filter((a) => a.agent !== "checks");
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
          {t(kind === "story" ? "uthStory" : "uthAnswer", lang).replace("{n}", String(agentCount(trace)))}
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
              {inStage.map(({ a, from }, i) => {
                const [name, role] = AGENTS[a.agent]?.[lang] ?? [a.agent, ""];
                const note = recoveryNote(a, kind, lang);
                return (
                  <div key={`${a.agent}-${i}`} className={`uth-agent${a.ok ? "" : " failed"}`}>
                    <div className="row">
                      <b>{name}</b>
                      <span className="uth-ms">{secs(a.ms)}</span>
                    </div>
                    <span className="uth-role">{role}</span>
                    {note && <span className="uth-recovery">{note}</span>}
                    <div className="uth-bar" aria-hidden="true">
                      <span style={{ left: `${(from / span) * 100}%`, width: `${Math.max(2, (a.ms / span) * 100)}%` }} />
                    </div>
                    {(a.ok || a.tools?.length) ? (
                      <div className="uth-tools">
                        {a.tools?.length
                          ? a.tools.map((tl, j) => <code key={j}>{tl.name}{argText(tl.args)}</code>)
                          : <span className="muted">{t("uthNoTools", lang)}</span>}
                      </div>
                    ) : null}
                    {(a.in || a.out) ? (
                      <span className="uth-meta">{(a.in ?? 0).toLocaleString()} in · {(a.out ?? 0).toLocaleString()} out{a.model ? ` · ${a.model}` : ""}</span>
                    ) : a.model ? <span className="uth-meta">{a.model}</span> : null}
                  </div>
                );
              })}
            </div>
          );
        })}
        {checks && (
          <div className="uth-checks">
            <div className="eyebrow">{t("uthChecks", lang)}</div>
            {checks.fixes?.length ? (
              <>
                <span className="uth-role">{t("uthChecksFixed", lang).replace("{n}", String(checks.checks ?? 0))}</span>
                <ul>{checks.fixes.map((f) => <li key={f}>{fixText(f, lang)}</li>)}</ul>
              </>
            ) : (
              <span className="uth-role">{t("uthChecksOk", lang).replace("{n}", String(checks.checks ?? 0))}</span>
            )}
          </div>
        )}
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
