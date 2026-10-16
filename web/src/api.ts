import type { AskAnswer, Call, ClubRef, LeaderRow, MatchSnapshot, MatchSummary, Moment, User, Impact, BigMoment } from "./types";

export const API_BASE: string = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* not json */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  clubs: () => req<ClubRef[]>("/api/clubs"),
  matches: () => req<MatchSummary[]>("/api/matches"),
  match: (id: string) => req<MatchSnapshot>(`/api/matches/${id}`),
  moments: (id: string) => req<BigMoment[]>(`/api/matches/${id}/moments`),
  replay: (id: string, body: { user_id: string; from_minute: number }) =>
    req<{ room_id: string; match_id: string; from_minute: number }>(`/api/matches/${id}/replay`, { method: "POST", body: JSON.stringify(body) }),
  listened: (id: string, body: { user_id: string }) =>
    req<{ events: unknown[] }>(`/api/matches/${id}/listened`, { method: "POST", body: JSON.stringify(body) }),
  motm: (id: string, body: { user_id: string; player_id: string }) =>
    req<Impact>(`/api/matches/${id}/motm`, { method: "POST", body: JSON.stringify(body) }),
  believe: (id: string, body: { user_id: string; side: number }) =>
    req<{ side: number; spell: number; count: number; new: boolean }>(`/api/matches/${id}/believe`, { method: "POST", body: JSON.stringify(body) }),
  speechStatus: () => req<{ azure: boolean }>("/api/speech"),
  speechUrl: (q: { kind: "story" | "answer"; id: string; lang: string; match_id?: string }) =>
    `${API_BASE}/api/speech/audio?${new URLSearchParams(Object.entries(q).filter(([, v]) => v) as [string, string][])}`,
  story: (id: string) => req<Moment[]>(`/api/matches/${id}/story`),
  ask: (id: string, body: { user_id: string; question: string; lang: string }) =>
    req<AskAnswer>(`/api/matches/${id}/ask`, { method: "POST", body: JSON.stringify(body) }),
  createUser: (name: string, club_id: string | null) =>
    req<User>("/api/users", { method: "POST", body: JSON.stringify({ name, club_id }) }),
  user: (id: string) => req<User>(`/api/users/${id}`),
  updateUser: (id: string, prefs: Partial<Pick<User, "name" | "club_id" | "persona" | "lang">>) =>
    req<User>(`/api/users/${id}`, { method: "PATCH", body: JSON.stringify(prefs) }),
  activity: (id: string, kind: "read_story" | "halftime", lang?: string) =>
    req<{ ok: boolean; user: User | null }>(`/api/users/${id}/activity?kind=${kind}${lang ? `&lang=${lang}` : ""}`, { method: "POST" }),
  calls: (id: string) => req<Call[]>(`/api/users/${id}/calls`),
  placeCall: (body: { user_id: string; market_id: string; option_id: string; stake: number; confidence?: number }) =>
    req<{ call: Call; user: User }>("/api/calls", { method: "POST", body: JSON.stringify(body) }),
  leaderboard: (code?: string) =>
    req<{ code: string | null; name: string; rows: LeaderRow[] }>(`/api/leaderboard${code ? `?code=${code}` : ""}`),
  createLeague: (user_id: string, name: string) =>
    req<{ code: string; name: string }>("/api/leagues", { method: "POST", body: JSON.stringify({ user_id, name }) }),
  joinLeague: (user_id: string, code: string) =>
    req<{ code: string; name: string }>("/api/leagues/join", { method: "POST", body: JSON.stringify({ user_id, code }) }),
  negotiate: (user_id: string) => req<{ url: string }>(`/api/negotiate?user_id=${encodeURIComponent(user_id)}`),
};
