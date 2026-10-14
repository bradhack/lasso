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
  copy: string | null;
}

export interface MatchSnapshot extends MatchSummary {
  history: MeterPoint[];
  feed: FeedItem[];
  moments: Moment[];
  stats: { match_id: string; teams: [TeamStats, TeamStats] };
  markets: Market[];
}

export interface Mission {
  id: string;
  label: string;
  target: number;
  reward: number;
  progress: number;
  done: boolean;
}

export interface MomentCard {
  id: string;
  rarity: "bronze" | "silver" | "gold";
  title: string;
  pick: string;
  p: number;
  minute: number;
  match: string;
  score: [number, number];
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
  cards: MomentCard[];
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
}

export interface LeaderRow {
  rank: number;
  id: string;
  name: string;
  biscuits: number;
  streak: number;
  level: number;
}
