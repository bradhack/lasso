import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { setMeterName } from "./i18n";
import "@fontsource/barlow-condensed/500.css";
import "@fontsource/barlow-condensed/600.css";
import "@fontsource/barlow-condensed/700.css";
import "@fontsource/dm-sans/400.css";
import "@fontsource/dm-sans/500.css";
import "@fontsource/dm-sans/700.css";
import "@fontsource/sora/700.css";
import "./styles.css";

// Theme: ?theme=<name> (design reviews) or the viewer's saved choice; the default lives in :root.
const params = new URLSearchParams(location.search);
const theme = params.get("theme") ?? (() => { try { return localStorage.getItem("lasso-theme"); } catch { return null; } })();
if (theme) document.documentElement.dataset.theme = theme;
if (params.get("meter")) setMeterName(params.get("meter")!);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => undefined));
}
