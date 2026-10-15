/**
 * Keep open phones on the latest deploy. A single-page app keeps the code it loaded, so after a
 * deploy we check the page shell for a new bundle and reload, preferably when the app comes back
 * into view so nobody loses a call mid-tap.
 */
const current = () => document.querySelector<HTMLScriptElement>('script[type="module"][src*="/assets/"]')?.getAttribute("src") ?? "";

async function latest(): Promise<string> {
  const html = await fetch(`/?v=${Date.now()}`, { cache: "no-store" }).then((r) => r.text());
  return html.match(/\/assets\/index-[^"']+\.js/)?.[0] ?? "";
}

export function watchForUpdates(onReady: () => void) {
  const mine = current();
  if (!mine) return; // dev server
  let pending = false;
  const check = async () => {
    try {
      const next = await latest();
      if (next && next !== mine && !pending) {
        pending = true;
        if (document.visibilityState === "hidden") location.reload();
        else onReady();
      }
    } catch {
      /* offline; try again later */
    }
  };
  setInterval(check, 90_000);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible") return;
    if (pending) location.reload();
    else check();
  });
}
