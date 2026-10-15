/** Appearance: Midnight (dark) is the default; Ivory is the light mode. Saved per device. */
export type Appearance = "dark" | "light";
const KEY = "lasso-theme";
const THEME_COLOR: Record<string, string> = { "": "#0A1020", ivory: "#F5F2EB" };

export function applyTheme(theme: string | null) {
  const root = document.documentElement;
  if (theme) root.dataset.theme = theme;
  else delete root.dataset.theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", THEME_COLOR[theme ?? ""] ?? THEME_COLOR[""]);
}

export function savedTheme(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setAppearance(a: Appearance) {
  const theme = a === "light" ? "ivory" : null;
  try {
    if (theme) localStorage.setItem(KEY, theme);
    else localStorage.removeItem(KEY);
  } catch {
    /* private mode: still applies for this visit */
  }
  applyTheme(theme);
  window.dispatchEvent(new Event("lasso-theme"));
}

export function currentAppearance(): Appearance {
  return document.documentElement.dataset.theme === "ivory" ? "light" : "dark";
}
