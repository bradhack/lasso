export type Lang = "en" | "es" | "pt" | "fr";
export type Localized = Partial<Record<Lang, string>>;
export type Probs = { home: number; draw: number; away: number };

export interface ClubRef {
  club_id: string;
  name: string;
  short: string;
  monogram: string;
  primary: string;
  secondary: string;
}

export interface MatchSummary {
  match_id: string;
  status: "scheduled" | "live" | "half_time" | "finished";
  home: ClubRef;
  away: ClubRef;
  score: [number, number];
  reds: [number, number];
  period: number;
  clock: number;
  minute: number;
  probs: Probs;
  prematch: Probs;
  cards?: Booking[];
  var?: VarCheck | null;
  /** Touch the sign: per side, the open "behind" spell and how many fans believe. */
  believe?: ({ spell: number; count: number } | null)[];
  /** The season race this match matters most to (from the season outlook). */
  race?: Zone | "none" | null;
}

/** Player of the Match: one player's impact on their team's chances (win plus half a draw), in points. */
export interface ImpactPlayer {
  id: string;
  name: string;
  short: string;
  team: 0 | 1;
  impact: number;
  goals: number;
  assists: number;
  shots: number;
  saves: number;
  reds: number;
  best: { kind: "goal" | "assist" | "chance" | "save" | "red"; minute: number; pts: number } | null;
}

export interface Impact {
  players: ImpactPlayer[];
  open: boolean;
  winner: string | null;
  votes: Record<string, number>;
  voters: number;
  mine: string | null;
}

export type Zone = "title" | "top4" | "relegation";
export type Result = "home" | "draw" | "away";

export interface SeasonOdds {
  title: number;
  top4: number;
  relegation: number;
  avg_pos: number;
}

export interface TableRow {
  club_id: string;
  name: string;
  short: string;
  primary: string;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  gf: number;
  ga: number;
  gd: number;
  pts: number;
}

/** Season outlook: the table before this match, and every club's odds for each result from `score`. */
export interface Season {
  season: number;
  matchday: number;
  sims: number;
  remaining: number;
  score: [number, number];
  table: TableRow[];
  odds: Record<Result, Record<string, SeasonOdds>>;
  kickoff: Record<string, SeasonOdds>;
  stakes: Record<"home" | "away", { zone: Zone | "none"; spread: number }>;
}

/** A booking on the scoreboard: team (0 home, 1 away), yellow or red, surname, minute. */
export interface Booking {
  k: 0 | 1;
  c: "y" | "r";
  p: string;
  m: number;
}

export interface MeterPoint extends Probs {
  elapsed: number;
  period: number;
  clock: number;
}

export interface Driver {
  component: "goals" | "red_cards" | "chances" | "clock";
  delta: number;
  label: Localized;
}

export interface AgentTrace {
  agent: string;
  ms: number;
  ok: boolean;
  stage?: number;
  start?: number; // epoch seconds
  tools?: { name: string; args?: Record<string, unknown> }[];
  in?: number;
  out?: number;
  reasoning?: number;
  model?: string;
}

export interface Moment {
  moment_id: string;
  match_id: string;
  trigger: string;
  minute: number;
  focus: 0 | 1;
  before: Probs;
  after: Probs;
  drivers: Driver[];
  score: [number, number];
  headline: Localized;
  story: Localized;
  analyst: Localized;
  club_lines: { home?: Localized; away?: Localized };
  source: "template" | "agents";
  agent_trace?: AgentTrace[];
  latency_ms?: number;
}

export interface AskAnswer {
  ask_id: string;
  question: string;
  answer: string;
  followups: string[];
  source: "agents" | "gaffer";
  trace: AgentTrace[];
  minute: number;
  latency_ms: number;
  pending?: boolean;
}

export interface FeedItem {
  seq: number;
  type: string;
  minute: number;
  team: 0 | 1 | null;
  player: string;
  text: string;
  xg?: number;
  speed?: number;
  on?: boolean; // a chance on target
  off?: string; // a substitution: who came off
  reason?: string; // VAR: offside, handball or foul
  decision?: "stands" | "ruled_out";
  score?: [number, number];
}

/** A VAR check in progress: the Gaffer's Gauge both ways. */
export interface VarCheck {
  status: "checking";
  team: 0 | 1;
  player: string;
  reason: string;
  minute: number;
  stands: Probs;
  ruled_out: Probs;
}

export interface VarDecision {
  status: "stands" | "ruled_out";
  team: 0 | 1;
  player: string;
  reason: string;
  minute: number;
  at: number; // when it arrived (ms), so the result shows for a few seconds
}

export interface TeamStats {
  club_id: string;
  possession: number;
  field_tilt: number;
  pass_accuracy: number;
  avg_pass_difficulty: number;
  passes: number;
  shots: number;
  on_target: number;
  xg: number;
  goals: number;
  corners: number;
  fouls: number;
  yellows: number;
  reds: number;
  fastest_shot_kmh: number;
  longest_pass_m: number;
  xg_last_10: number;
}

export interface MarketOption {
  id: string;
  label: string;
  p: number;
  multiplier: number;
}

export interface Market {
  market_id: string;
  match_id: string;
  question: string;
  options: MarketOption[];
  closes: { period: number; clock: number };
  status: "open" | "closed" | "settled";
  result: string | null;
  kind: string;
  copy: string | Localized | null;
  params?: { team?: string; until?: number };
}

/** One ball action for the Touchline view. Home attacks left to right; pitch is 105 x 68 m. */
export interface Touch {
  s: number; // event sequence
  t: "kickoff" | "pass" | "shot" | "tackle" | "interception" | "save" | "corner" | "foul" | "yellow_card" | "red_card" | "substitution";
  k: 0 | 1; // acting team: 0 home, 1 away
  m: number; // match minute
  p: string; // player
  x?: number;
  y?: number;
  ex?: number; // pass end
  ey?: number;
  o?: boolean; // pass completed
  r?: string; // pass receiver
  xg?: number;
  g?: boolean; // goal
  on?: boolean; // on target
  pos: 0 | 1 | null; // possession after this action
}

export interface BelieveWin {
  side: 0 | 1;
  count: number;
  minute: number;
}

export interface MatchSnapshot extends MatchSummary {
  believe_won?: BelieveWin | null;
  var_decision?: VarDecision | null;
  history: MeterPoint[];
  touches?: Touch[];
  shots?: Touch[];
  possession?: 0 | 1 | null;
  feed: FeedItem[];
  moments: Moment[];
  stats: { match_id: string; teams: [TeamStats, TeamStats] };
  markets: Market[];
  season?: Season | null;
  impact?: Impact | null;
}

export interface Mission {
  id: string;
  label: string;
  target: number;
  reward: number;
  progress: number;
  done: boolean;
}

export interface Sticker {
  id: string;
  tier: "bronze" | "silver" | "gold";
  name: Record<string, string>;
  how: Record<string, string>;
  earned: boolean;
  count: number;
  detail?: string | null;
}

export interface User {
  id: string;
  name: string;
  club_id: string | null;
  persona: "fan" | "analyst";
  lang: Lang;
  biscuits: number;
  xp: number;
  level: number;
  next_level_xp: number;
  streak: number;
  best_streak: number;
  calls_total: number;
  calls_won: number;
  calibration_points: number;
  leagues: string[];
  goldfish_available: boolean;
  stickers: Sticker[];
  missions: Mission[];
}

export interface Call {
  id: string;
  market_id: string;
  question: string;
  option_id: string;
  label: string;
  stake: number;
  multiplier: number;
  p: number;
  status: "open" | "won" | "lost";
  payout: number;
  minute: number;
  goldfish?: boolean;
  match_id?: string;
  placed_at?: number;
  kind?: string;
  params?: { team?: string; until?: number };
}

export interface LeaderRow {
  rank: number;
  id: string;
  name: string;
  biscuits: number;
  streak: number;
  level: number;
}
