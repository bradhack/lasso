import type { Call, ClubRef, LeaderRow, MatchSnapshot, MatchSummary, User } from "./types";

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
