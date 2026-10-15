import type { Lang, Localized } from "./types";

const S = {
  live: { en: "Live", es: "En vivo", pt: "Ao vivo", fr: "En direct" },
  leagues: { en: "Leagues", es: "Ligas", pt: "Ligas", fr: "Ligues" },
  cards: { en: "Stickers", es: "Cromos", pt: "Figurinhas", fr: "Vignettes" },
  me: { en: "Me", es: "Yo", pt: "Eu", fr: "Moi" },
  liveNow: { en: "Live now", es: "En vivo ahora", pt: "Ao vivo agora", fr: "En direct" },
  upNext: { en: "Up next", es: "A continuación", pt: "A seguir", fr: "À suivre" },
  fullTime: { en: "Full time", es: "Final", pt: "Encerrado", fr: "Terminé" },
  halfTime: { en: "Halftime", es: "Descanso", pt: "Intervalo", fr: "Mi-temps" },
  meter: { en: "Gaffer's Gauge", es: "Medidor del Gaffer", pt: "Medidor do Gaffer", fr: "Jauge du Gaffer" },
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
    en: "Next challenge soon. Keep an eye on the {meter}.",
    es: "Pronto llega otro reto. Atento al {meter}.",
    pt: "Novo desafio em breve. De olho no {meter}.",
    fr: "Prochain défi bientôt. Surveille la {meter}.",
  },
  heroA: { en: "WATCH SMARTER.", es: "MIRA MEJOR.", pt: "ASSISTA MELHOR.", fr: "REGARDE MIEUX." },
  heroB: { en: "CALL IT FIRST.", es: "PREDÍCELO PRIMERO.", pt: "CRAVE PRIMEIRO.", fr: "ANNONCE-LE AVANT." },
  heroSub: {
    en: "Lasso shows your team's chances live, tells you in plain English why they just changed, and challenges you to predict what happens next against the Gaffer, our AI. Free to play.",
    es: "Lasso muestra en vivo las opciones de tu equipo, te explica con palabras claras por qué acaban de cambiar y te reta a predecir lo que viene contra el Gaffer, nuestra IA. Gratis.",
    pt: "O Lasso mostra ao vivo as chances do seu time, explica em palavras simples por que elas acabaram de mudar e desafia você a prever o que vem a seguir contra o Gaffer, nossa IA. Grátis.",
    fr: "Lasso affiche en direct les chances de ton équipe, t'explique simplement pourquoi elles viennent de bouger et te défie de prédire la suite face au Gaffer, notre IA. Gratuit.",
  },
  obSub: {
    en: "Free to play. Your Biscuit Tin starts with 1,000 biscuits (points with no cash value). Call what happens next, build a streak, fill your sticker book.",
    es: "Gratis. Tu lata de galletas empieza con 1.000 (puntos sin valor en dinero). Predice lo que viene, haz una racha y llena tu álbum.",
    pt: "Grátis. Sua lata de biscoitos começa com 1.000 (pontos sem valor em dinheiro). Preveja o que vem, faça uma sequência e complete seu álbum.",
    fr: "Gratuit. Ta boîte à biscuits démarre avec 1 000 biscuits (des points sans valeur monétaire). Prédis la suite, enchaîne les séries, remplis ton album.",
  },
  clubHint: {
    en: "(optional, for your club's angle on every swing)", es: "(opcional, para ver cada cambio desde tu club)",
    pt: "(opcional, para ver cada virada pelo lado do seu clube)", fr: "(facultatif, pour voir chaque bascule côté club)",
  },
  biscuitTin: { en: "Biscuit Tin", es: "Lata de galletas", pt: "Lata de biscoitos", fr: "Boîte à biscuits" },
  behind: { en: "{team} are behind. Believe.", es: "{team} va perdiendo. A creer.", pt: "{team} está perdendo. Acredite.", fr: "{team} est mené. Y croire." },
  backedIt: { en: "You backed the comeback.", es: "Apostaste por la remontada.", pt: "Você apostou na virada.", fr: "Tu as cru au retour." },
  cameBack: { en: "{team} came back.", es: "{team} remontó.", pt: "{team} reagiu.", fr: "{team} est revenu." },
  menLeft: { en: "{n} men", es: "{n} jugadores", pt: "{n} jogadores", fr: "{n} joueurs" },
  redCards: { en: "Red card: playing a player short", es: "Roja: juega con uno menos", pt: "Vermelho: joga com um a menos", fr: "Carton rouge : joue à dix" },
  goldfish: { en: "Goldfish", es: "Goldfish", pt: "Goldfish", fr: "Goldfish" },
  gfReady: { en: "Goldfish ready", es: "Goldfish listo", pt: "Goldfish pronto", fr: "Goldfish prêt" },
  gfUsed: { en: "Goldfish used. Back on Monday.", es: "Goldfish usado. Vuelve el lunes.", pt: "Goldfish usado. Volta na segunda.", fr: "Goldfish utilisé. Retour lundi." },
  gfToast: {
    en: "Short memory. That miss is forgotten and your {n} streak lives on.",
    es: "Memoria corta. Ese fallo queda olvidado y tu racha de {n} sigue viva.",
    pt: "Memória curta. Esse erro foi esquecido e sua sequência de {n} continua.",
    fr: "Mémoire courte. Ce raté est oublié et ta série de {n} continue.",
  },
  streakTitle: { en: "Your streak", es: "Tu racha", pt: "Sua sequência", fr: "Ta série" },
  streakHow: {
    en: "Win calls in a row to build a streak. At 3 in a row your wins pay 1.25x, and at 5 they pay 1.5x.",
    es: "Acierta seguido para hacer racha. Con 3 seguidos tus aciertos pagan 1,25x y con 5, 1,5x.",
    pt: "Acerte em sequência para criar uma série. Com 3 seguidos seus acertos pagam 1,25x e com 5, 1,5x.",
    fr: "Enchaîne les bons pronos pour faire une série. À 3 de suite, tes gains passent à 1,25x, et à 5, à 1,5x.",
  },
  gfHow: {
    en: "Once a week, your Goldfish forgets one missed call, so a streak of 3 or more keeps going. It comes back every Monday.",
    es: "Una vez por semana, tu Goldfish olvida un fallo, así que una racha de 3 o más sigue viva. Vuelve cada lunes.",
    pt: "Uma vez por semana, seu Goldfish esquece um erro, então uma sequência de 3 ou mais continua. Ele volta toda segunda.",
    fr: "Une fois par semaine, ton Goldfish oublie un prono raté, et une série de 3 ou plus continue. Il revient chaque lundi.",
  },
  inARow: { en: "in a row", es: "seguidos", pt: "seguidos", fr: "de suite" },
  gotIt: { en: "Got it", es: "Entendido", pt: "Entendi", fr: "Compris" },
  myCalls: { en: "Your calls", es: "Tus pronósticos", pt: "Seus palpites", fr: "Tes pronos" },
  callsSummary: { en: "{n} calls · {w} won · {o} live", es: "{n} pronósticos · {w} acertados · {o} en juego", pt: "{n} palpites · {w} certos · {o} em jogo", fr: "{n} pronos · {w} gagnés · {o} en cours" },
  stOpen: { en: "Live", es: "En juego", pt: "Em jogo", fr: "En cours" },
  stWon: { en: "Won", es: "Acertado", pt: "Certo", fr: "Gagné" },
  stLost: { en: "Missed", es: "Fallado", pt: "Errou", fr: "Raté" },
  stSaved: { en: "Missed · Goldfish saved your streak", es: "Fallado · el Goldfish salvó tu racha", pt: "Errou · o Goldfish salvou sua sequência", fr: "Raté · le Goldfish a sauvé ta série" },
  noCalls: { en: "No calls yet. Open a live match and make your first one.", es: "Aún no hay pronósticos. Abre un partido en vivo y haz el primero.", pt: "Nenhum palpite ainda. Abra um jogo ao vivo e faça o primeiro.", fr: "Pas encore de prono. Ouvre un match en direct et lance-toi." },
  showAll: { en: "Show all", es: "Ver todo", pt: "Ver tudo", fr: "Tout voir" },
  teamTalk: { en: "Halftime team talk", es: "Charla del descanso", pt: "Preleção do intervalo", fr: "Causerie de la mi-temps" },
  fanHint: { en: "Plain-English stories and your club's angle", es: "Historias claras y el punto de vista de tu club", pt: "Histórias simples e o lado do seu clube", fr: "Des récits simples et l'angle de ton club" },
  analystHint: { en: "xG, field tilt and the full breakdown of every swing", es: "xG, dominio territorial y el desglose de cada cambio", pt: "xG, domínio territorial e o detalhamento de cada virada", fr: "xG, territoire et le détail de chaque bascule" },
  newSticker: { en: "New sticker", es: "Nuevo cromo", pt: "Nova figurinha", fr: "Nouvelle vignette" },
  stickerHead: { en: "YOUR STICKER BOOK", es: "TU ÁLBUM", pt: "SEU ÁLBUM", fr: "TON ALBUM" },
  stickerSub: {
    en: "Earn them by calling the game well: first calls, long shots, late winners and comebacks.",
    es: "Gánalos leyendo bien el partido: primeros pronósticos, sorpresas, goles al final y remontadas.",
    pt: "Ganhe lendo bem o jogo: primeiros palpites, zebras, gols no fim e viradas.",
    fr: "Gagne-les en lisant bien le match : premiers pronos, coups de poker, buts tardifs et remontadas.",
  },
  gold: { en: "Gold", es: "Oro", pt: "Ouro", fr: "Or" },
  silver: { en: "Silver", es: "Plata", pt: "Prata", fr: "Argent" },
  bronze: { en: "Bronze", es: "Bronce", pt: "Bronze", fr: "Bronze" },
  hopeLine: { en: "It's the hope that kills you.", es: "Lo que mata es la esperanza.", pt: "O que mata é a esperança.", fr: "C'est l'espoir qui fait mal." },
  hopeSub: { en: "So close. The Gaffer had it at", es: "Por poco. El Gaffer lo veía al", pt: "Por pouco. O Gaffer via em", fr: "Si près. Le Gaffer le voyait à" },
  touchline: { en: "Touchline", es: "Desde la banda", pt: "Beira do campo", fr: "Bord du terrain" },
  ball: { en: "ball", es: "con el balón", pt: "com a bola", fr: "au ballon" },
  tShot: { en: "Shot", es: "Tiro", pt: "Chute", fr: "Tir" },
  tGoal: { en: "GOAL", es: "GOL", pt: "GOL", fr: "BUT" },
  tSaved: { en: "saved", es: "atajado", pt: "defendido", fr: "arrêté" },
  tOff: { en: "off target", es: "desviado", pt: "para fora", fr: "non cadré" },
  tTackle: { en: "Tackle", es: "Entrada", pt: "Desarme", fr: "Tacle" },
  tInterception: { en: "Interception", es: "Intercepción", pt: "Interceptação", fr: "Interception" },
  tFoul: { en: "Foul", es: "Falta", pt: "Falta", fr: "Faute" },
  tCorner: { en: "Corner", es: "Córner", pt: "Escanteio", fr: "Corner" },
  tSave: { en: "Save", es: "Parada", pt: "Defesa", fr: "Arrêt" },
  tYellow: { en: "Yellow card", es: "Amarilla", pt: "Amarelo", fr: "Carton jaune" },
  tRed: { en: "Red card", es: "Roja", pt: "Vermelho", fr: "Carton rouge" },
  tSub: { en: "Substitution", es: "Cambio", pt: "Substituição", fr: "Remplacement" },
  tKickoff: { en: "Kickoff", es: "Saque inicial", pt: "Saída de bola", fr: "Coup d'envoi" },
  tMiss: { en: "Pass cut out", es: "Pase cortado", pt: "Passe cortado", fr: "Passe coupée" },
  vShots: { en: "Shots", es: "Tiros", pt: "Chutes", fr: "Tirs" },
  goalWord: { en: "Goal", es: "Gol", pt: "Gol", fr: "But" },
  onTarget: { en: "on target", es: "a puerta", pt: "no alvo", fr: "cadrés" },
  goalsWord: { en: "goals", es: "goles", pt: "gols", fr: "buts" },
  sizeXg: { en: "Size = xG", es: "Tamaño = xG", pt: "Tamanho = xG", fr: "Taille = xG" },
  hide: { en: "Hide", es: "Ocultar", pt: "Ocultar", fr: "Masquer" },
  show: { en: "Show", es: "Mostrar", pt: "Mostrar", fr: "Afficher" },
  appearance: { en: "Appearance", es: "Apariencia", pt: "Aparência", fr: "Apparence" },
  dark: { en: "Dark", es: "Oscuro", pt: "Escuro", fr: "Sombre" },
  light: { en: "Light", es: "Claro", pt: "Claro", fr: "Clair" },
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
} satisfies Record<string, Record<Lang, string>>;

export type Key = keyof typeof S;

// Design reviews can preview another name for the live win-chance meter with ?meter=<name>.
let meterOverride = "";
export function setMeterName(name: string) {
  meterOverride = name.trim().slice(0, 30);
}

export function t(key: Key, lang: Lang): string {
  if (key === "meter" && meterOverride) return meterOverride;
  const text = S[key][lang] ?? S[key].en;
  return text.includes("{meter}") ? text.replace("{meter}", t("meter", lang)) : text;
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
