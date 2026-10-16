import { create } from "zustand";
import { api } from "./api";
import { Realtime } from "./realtime";
import type { AskAnswer, Call, ClubRef, Lang, Market, MatchSnapshot, MatchSummary, Moment, Sticker, Touch, User } from "./types";

export type Toast =
  | { id: number; kind: "win"; call: Call }
  | { id: number; kind: "loss"; call: Call }
  | { id: number; kind: "sticker"; sticker: Sticker }
  | { id: number; kind: "hope"; call: Call }
  | { id: number; kind: "mission"; label: string; reward: number; mission?: string }
  | { id: number; kind: "goldfish"; streak: number }
  | { id: number; kind: "believe"; team: string; reward: number }
  | { id: number; kind: "error"; text: string }
  | { id: number; kind: "update" };

type ToastInput =
  | { kind: "win"; call: Call }
  | { kind: "loss"; call: Call }
  | { kind: "sticker"; sticker: Sticker }
  | { kind: "hope"; call: Call }
  | { kind: "mission"; label: string; reward: number; mission?: string }
  | { kind: "goldfish"; streak: number }
  | { kind: "believe"; team: string; reward: number }
  | { kind: "error"; text: string }
  | { kind: "update" };

interface State {
  user: User | null;
  clubs: Record<string, ClubRef>;
  matches: MatchSummary[];
  snapshots: Record<string, MatchSnapshot>;
  calls: Record<string, Call>; // by market_id
  asks: Record<string, AskAnswer[]>;
  believed: Record<string, boolean>;
  speechAzure: boolean; // Listen: Azure AI Speech is on (otherwise the phone's own voice) // Touch the sign: `${match}:${side}:${spell}` this fan touched // Ask the Gaffer, by match_id (only the asker sees these)
  toasts: Toast[];
  connected: boolean;
  rt: Realtime | null;
  lang: Lang;
  init: () => Promise<void>;
  signUp: (name: string, club: string | null, persona: User["persona"], lang: Lang) => Promise<void>;
  setUser: (u: User) => void;
  updatePrefs: (p: Partial<Pick<User, "name" | "club_id" | "persona" | "lang">>) => Promise<void>;
  watch: (matchId: string) => Promise<void>;
  setAsks: (matchId: string, fn: (list: AskAnswer[]) => AskAnswer[]) => void;
  touchSign: (matchId: string, side: 0 | 1) => Promise<void>;
  unwatch: (matchId: string) => void;
  placeCall: (m: Market, optionId: string, stake: number) => Promise<void>;
  toast: (t: ToastInput) => void;
  dismiss: (id: number) => void;
}

const KEY = "lasso.user";
const MAX_MOMENTS = 60;
let toastId = 1;

function readId(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}
function writeId(id: string) {
  try {
    localStorage.setItem(KEY, id);
  } catch {
    /* private mode */
  }
}

export const useStore = create<State>((set, get) => ({
  user: null,
  clubs: {},
  matches: [],
  snapshots: {},
  calls: {},
  asks: {},
  believed: {},
  speechAzure: false,
  toasts: [],
  connected: false,
  rt: null,
  lang: "en",

  init: async () => {
    const [clubs, matches] = await Promise.all([api.clubs(), api.matches()]);
    api.speechStatus().then((r) => set({ speechAzure: r.azure })).catch(() => undefined);
    set({ clubs: Object.fromEntries(clubs.map((c) => [c.club_id, c])), matches });
    const id = readId();
    if (id) {
      try {
        const user = await api.user(id);
        set({ user, lang: user.lang });
        await connect(user.id);
        const calls = await api.calls(user.id);
        set({ calls: Object.fromEntries(calls.map((c) => [c.market_id, c])) });
      } catch {
        /* stale id: onboarding will create a new user */
      }
    }
  },

  signUp: async (name, club, persona, lang) => {
    let user = await api.createUser(name || "Fan", club);
    user = await api.updateUser(user.id, { persona, lang });
    writeId(user.id);
    set({ user, lang });
    await connect(user.id);
  },

  setUser: (u) => set({ user: u, lang: u.lang }),

  updatePrefs: async (p) => {
    const u = get().user;
    if (!u) return;
    const user = await api.updateUser(u.id, p);
    set({ user, lang: user.lang });
  },

  watch: async (matchId) => {
    get().rt?.join(`match:${matchId}`);
    // The snapshot carries the latest few stories; the match story needs all of them.
    const [snap, story] = await Promise.all([api.match(matchId), api.story(matchId).catch(() => null)]);
    if (story?.length) snap.moments = story.slice(-MAX_MOMENTS);
    set((s) => ({ snapshots: { ...s.snapshots, [matchId]: snap } }));
  },

  touchSign: async (matchId, side) => {
    const u = get().user;
    const spell = get().snapshots[matchId]?.believe?.[side];
    if (!u || !spell) return;
    const key = `${matchId}:${side}:${spell.spell}`;
    set((s) => ({ believed: { ...s.believed, [key]: true } }));
    navigator.vibrate?.(25);
    try {
      const r = await api.believe(matchId, { user_id: u.id, side });
      patchSnap(matchId, (s) => ({
        believe: (s.believe ?? [null, null]).map((b, i) => (i === side && b ? { ...b, count: Math.max(b.count, r.count) } : b)),
      }));
    } catch {
      set((s) => ({ believed: { ...s.believed, [key]: false } }));
    }
  },

  setAsks: (matchId, fn) => set((s) => ({ asks: { ...s.asks, [matchId]: fn(s.asks[matchId] ?? []) } })),

  unwatch: (matchId) => get().rt?.leave(`match:${matchId}`),

  placeCall: async (m, optionId, stake) => {
    const u = get().user;
    if (!u) return;
    try {
      const { call, user } = await api.placeCall({ user_id: u.id, market_id: m.market_id, option_id: optionId, stake });
      set((s) => ({ user, calls: { ...s.calls, [m.market_id]: call } }));
      navigator.vibrate?.(30);
    } catch (e) {
      get().toast({ kind: "error", text: (e as Error).message });
    }
  },

  toast: (t) => {
    const id = toastId++;
    set((s) => ({ toasts: [...s.toasts, { ...t, id } as Toast] }));
    setTimeout(() => get().dismiss(id), t.kind === "error" ? 3500 : t.kind === "update" ? 30000 : 5200);
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) })),
}));

async function connect(userId: string) {
  const prev = useStore.getState().rt;
  prev?.stop();
  const rt = new Realtime(userId);
  rt.onStatus((c) => useStore.setState({ connected: c }));
  rt.on(onMessage);
  rt.join("lobby");
  useStore.setState({ rt });
  await rt.start();
}

function patchSnap(matchId: string, fn: (s: MatchSnapshot) => Partial<MatchSnapshot>) {
  useStore.setState((st) => {
    const snap = st.snapshots[matchId];
    if (!snap) return {};
    return { snapshots: { ...st.snapshots, [matchId]: { ...snap, ...fn(snap) } } };
  });
}

function upsertMarket(list: Market[], m: Market): Market[] {
  const i = list.findIndex((x) => x.market_id === m.market_id);
  if (i < 0) return [...list, m].slice(-6);
  const copy = list.slice();
  copy[i] = m;
  return copy;
}

function upsertMoment(list: Moment[], m: Moment): Moment[] {
  const i = list.findIndex((x) => x.moment_id === m.moment_id);
  if (i < 0) return [...list, m].slice(-MAX_MOMENTS);
  const copy = list.slice();
  copy[i] = m;
  return copy;
}

function onMessage(d: any) {
  const st = useStore.getState();
  switch (d?.type) {
    case "status": {
      const m: MatchSummary = d.match;
      useStore.setState((s) => ({
        matches: s.matches.some((x) => x.match_id === m.match_id)
          ? s.matches.map((x) => (x.match_id === m.match_id ? m : x))
          : [...s.matches, m],
      }));
      patchSnap(m.match_id, () => ({ ...m }));
      break;
    }
    case "reset":
      patchSnap(d.match.match_id, () => ({ believe_won: null, var_decision: null }));
      if (st.snapshots[d.match.match_id]) st.watch(d.match.match_id);
      break;
    case "meter":
      patchSnap(d.match_id, (s) => ({
        history: [...s.history, d.point].slice(-500),
        touches: d.touches?.length ? [...(s.touches ?? []), ...d.touches].slice(-60) : s.touches,
        shots: d.touches?.some((x: Touch) => x.t === "shot") ? [...(s.shots ?? []), ...d.touches.filter((x: Touch) => x.t === "shot")] : s.shots,
        possession: d.possession ?? s.possession,
        believe: d.believe ?? s.believe,
        probs: { home: d.point.home, draw: d.point.draw, away: d.point.away },
        score: d.score,
        minute: d.minute,
        period: d.period,
        clock: d.clock,
        status: d.status,
      }));
      break;
    case "event":
      patchSnap(d.match_id, (s) => ({ feed: [...s.feed, d.event].slice(-60) }));
      break;
    case "moment":
    case "moment_update":
      patchSnap(d.moment.match_id, (s) => ({ moments: upsertMoment(s.moments, d.moment) }));
      break;
    case "var":
      patchSnap(d.match_id, () => ({
        var: d.var ?? null,
        ...(d.decision ? { var_decision: { ...d.decision, at: Date.now() } } : {}),
      }));
      break;
    case "believe":
      patchSnap(d.match_id, () => ({ believe_won: { side: d.side, count: d.count, minute: d.minute } }));
      break;
    case "believe_paid":
      if (st.user && typeof d.biscuits === "number") useStore.setState({ user: { ...st.user, biscuits: d.biscuits } });
      st.toast({ kind: "believe", team: d.team, reward: d.reward });
      break;
    case "stats":
      patchSnap(d.stats.match_id, () => ({ stats: d.stats }));
      break;
    case "market_open":
    case "market_closed":
    case "market_settled":
      patchSnap(d.market.match_id, (s) => ({ markets: upsertMarket(s.markets, d.market) }));
      break;
    case "call_settled": {
      const call: Call = d.call;
      useStore.setState((s) => ({ user: d.user, calls: { ...s.calls, [call.market_id]: call } }));
      // A long shot that just missed gets the terrace consolation instead of a plain loss.
      st.toast(call.status === "won" ? { kind: "win", call } : call.p < 0.15 ? { kind: "hope", call } : { kind: "loss", call });
      break;
    }
    case "sticker":
      st.toast({ kind: "sticker", sticker: { ...d.sticker, earned: true, count: 1 } });
      break;
    case "mission_complete":
      if (st.user && typeof d.biscuits === "number") useStore.setState({ user: { ...st.user, biscuits: d.biscuits } });
      st.toast({ kind: "mission", label: d.label, reward: d.reward, mission: d.mission });
      break;
    case "goldfish":
      st.toast({ kind: "goldfish", streak: d.streak });
      break;
  }
}
