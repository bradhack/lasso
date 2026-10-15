import { useEffect, useState } from "react";
import { BottomNav, Toasts, TopBar } from "./components/Chrome";
import { Onboarding } from "./components/Onboarding";
import { Lobby, MatchPage } from "./pages/Live";
import { Overlay } from "./pages/Overlay";
import { CardsPage, Leagues, Profile } from "./pages/Social";
import { useStore } from "./store";
import type { Lang } from "./types";

function useHashRoute() {
  const [hash, setHash] = useState(() => location.hash.replace(/^#\/?/, ""));
  useEffect(() => {
    const on = () => {
      setHash(location.hash.replace(/^#\/?/, ""));
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return hash;
}

export default function App() {
  const route = useHashRoute();
  const init = useStore((s) => s.init);
  const user = useStore((s) => s.user);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    init().then(() => setReady(true)).catch((e) => setError(String(e)));
  }, [init]);

  const [page, arg, extra] = route.split("/");

  if (page === "overlay" && arg) {
    const lang = (extra as Lang) || "en";
    return ready ? <OverlayGate id={arg} lang={lang} /> : null;
  }
  if (error) return <div className="app"><div className="page"><div className="empty">Can't reach the match server. Retrying shortly…</div></div></div>;
  if (!ready) return <div className="app"><div className="page"><div className="empty">Warming up…</div></div></div>;

  return (
    <div className="app">
      <TopBar />
      {page === "match" && arg ? <MatchPage id={arg} /> :
        page === "leagues" ? <Leagues /> :
        page === "cards" ? <CardsPage /> :
        page === "me" ? <Profile /> : <Lobby />}
      <BottomNav route={page ?? ""} />
      <Toasts />
      {!user && <Onboarding />}
    </div>
  );
}

function OverlayGate({ id, lang }: { id: string; lang: Lang }) {
  const user = useStore((s) => s.user);
  const signUp = useStore((s) => s.signUp);
  useEffect(() => {
    if (!user) signUp("Broadcast overlay", null, "fan", lang).catch(() => undefined);
  }, [user, signUp, lang]);
  return user ? <Overlay id={id} lang={lang} /> : null;
}
