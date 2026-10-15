import type { Lang, Localized } from "./types";

const S = {
  live: { en: "Live", es: "En vivo", pt: "Ao vivo", fr: "En direct" },
  leagues: { en: "Leagues", es: "Ligas", pt: "Ligas", fr: "Ligues" },
  cards: { en: "Cards", es: "Cartas", pt: "Cartas", fr: "Cartes" },
  me: { en: "Me", es: "Yo", pt: "Eu", fr: "Moi" },
  liveNow: { en: "Live now", es: "En vivo ahora", pt: "Ao vivo agora", fr: "En direct" },
  upNext: { en: "Up next", es: "A continuación", pt: "A seguir", fr: "À suivre" },
  fullTime: { en: "Full time", es: "Final", pt: "Encerrado", fr: "Terminé" },
  halfTime: { en: "Halftime", es: "Descanso", pt: "Intervalo", fr: "Mi-temps" },
  meter: { en: "Believe-o-Meter", es: "Believe-o-Meter", pt: "Believe-o-Meter", fr: "Believe-o-Meter" },
  draw: { en: "Draw", es: "Empate", pt: "Empate", fr: "Nul" },
  whyMoved: { en: "Why it moved", es: "Por qué cambió", pt: "Por que mudou", fr: "Pourquoi ça bouge" },
  callIt: { en: "Call it", es: "Predícelo", pt: "Crave", fr: "Pronostique" },
  gafferSays: { en: "The Gaffer says", es: "El Gaffer dice", pt: "O Gaffer diz", fr: "Le Gaffer dit" },
  beatIt: { en: "Beat it.", es: "Supéralo.", pt: "Supere.", fr: "Bats-le." },
  stake: { en: "Stake", es: "Apuesta", pt: "Aposta", fr: "Mise" },
  lassoIt: { en: "Lasso it", es: "Lázalo", pt: "Laçar", fr: "Lasso" },
  win: { en: "win", es: "gana", pt: "ganhe", fr: "gagne" },
  biscuits: { en: "biscuits", es: "galletas", pt: "biscoitos", fr: "biscuits" },
  lockedIn: { en: "Locked in", es: "Confirmado", pt: "Confirmado", fr: "Validé" },
  closes: { en: "Closes", es: "Cierra", pt: "Fecha", fr: "Ferme" },
  closed: { en: "Calls closed", es: "Cerrado", pt: "Fechado", fr: "Fermé" },
  waiting: {
    en: "Next challenge soon. Watch the Believe-o-Meter.",
    es: "Pronto llega otro reto. Mira el Believe-o-Meter.",
    pt: "Novo desafio em breve. De olho no Believe-o-Meter.",
    fr: "Prochain défi bientôt. Surveille le Believe-o-Meter.",
  },
  feed: { en: "Match feed", es: "Jugadas", pt: "Lances", fr: "Le fil du match" },
  analyst: { en: "Analyst view", es: "Vista analista", pt: "Visão analista", fr: "Vue analyste" },
  streak: { en: "streak", es: "racha", pt: "sequência", fr: "série" },
  calledIt: { en: "Called it!", es: "¡Acertaste!", pt: "Acertou!", fr: "Bien vu !" },
  notThisTime: { en: "Not this time", es: "Esta vez no", pt: "Não foi dessa vez", fr: "Pas cette fois" },
  agents: { en: "AI agents", es: "Agentes IA", pt: "Agentes de IA", fr: "Agents IA" },
  gaffer: { en: "Gaffer", es: "Gaffer", pt: "Gaffer", fr: "Gaffer" },
  missions: { en: "Today's missions", es: "Misiones de hoy", pt: "Missões de hoje", fr: "Missions du jour" },
  level: { en: "Level", es: "Nivel", pt: "Nível", fr: "Niveau" },
  settings: { en: "Settings", es: "Ajustes", pt: "Ajustes", fr: "Réglages" },
  language: { en: "Language", es: "Idioma", pt: "Idioma", fr: "Langue" },
  depth: { en: "How deep do you go?", es: "¿Cuánto detalle?", pt: "Quanto detalhe?", fr: "Quel niveau de détail ?" },
  fan: { en: "Fan", es: "Aficionado", pt: "Torcedor", fr: "Supporter" },
  analystMode: { en: "Analyst", es: "Analista", pt: "Analista", fr: "Analyste" },
  yourClub: { en: "Your club", es: "Tu club", pt: "Seu clube", fr: "Ton club" },
  noCards: {
    en: "Win a call the Gaffer doubted to earn your first moment card.",
    es: "Acierta algo que el Gaffer dudaba y gana tu primera carta.",
    pt: "Acerte algo que o Gaffer duvidava e ganhe sua primeira carta.",
    fr: "Réussis un pari dont le Gaffer doutait pour gagner ta première carte.",
  },
} satisfies Record<string, Record<Lang, string>>;

export type Key = keyof typeof S;

export function t(key: Key, lang: Lang): string {
  return S[key][lang] ?? S[key].en;
}

export function loc(text: Localized | undefined, lang: Lang): string {
  if (!text) return "";
  return text[lang] ?? text.en ?? "";
}

export const LANGS: { id: Lang; label: string }[] = [
  { id: "en", label: "English" },
  { id: "es", label: "Español" },
  { id: "pt", label: "Português" },
  { id: "fr", label: "Français" },
];
