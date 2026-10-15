import confetti from "canvas-confetti";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { t } from "../i18n";
import { useStore } from "../store";
import { Animated } from "./bits";
import { StickerBadge, stickerText } from "./Stickers";
import { Biscuit, CardsIcon, Fish, Flame, LassoMark, LiveIcon, Moon, Sun, Trophy, UserIcon } from "./Icons";
import { currentAppearance, setAppearance } from "../theme";

export function TopBar() {
  const user = useStore((s) => s.user);
  const connected = useStore((s) => s.connected);
  const lang = useStore((s) => s.lang);
  const [mode, setMode] = useState(currentAppearance);
  useEffect(() => {
    const sync = () => setMode(currentAppearance());
    window.addEventListener("lasso-theme", sync);
    return () => window.removeEventListener("lasso-theme", sync);
  }, []);
  const flip = () => setAppearance(mode === "dark" ? "light" : "dark");
  const [streakOpen, setStreakOpen] = useState(false);
  return (
    <header className="topbar">
      <a className="brand" href="#/" aria-label="Lasso home">
        <LassoMark />
        <span>lasso</span>
        <i className={`dot ${connected ? "pulse" : "off"}`} title={connected ? "live" : "reconnecting"} style={{ marginLeft: 2 }} />
      </a>
      {user && (
        <div className="pills">
          <span className="pill" title={t("biscuitTin", lang)}>
            <Biscuit />
            <Animated value={user.biscuits} />
          </span>
          <button className="pill gold" onClick={() => setStreakOpen(true)} aria-label={t("streakTitle", lang)}
            title={user.goldfish_available ? t("gfReady", lang) : t("gfUsed", lang)}>
            <Flame />
            <span>{user.streak}<span className="lbl"> {t("streak", lang)}</span></span>
            <span className={`fish${user.goldfish_available ? "" : " used"}`}><Fish size={15} /></span>
          </button>
          <button className="pill icon" onClick={flip} aria-label={mode === "dark" ? t("light", lang) : t("dark", lang)}
            title={mode === "dark" ? t("light", lang) : t("dark", lang)}>
            {mode === "dark" ? <Sun /> : <Moon />}
          </button>
        </div>
      )}
      {user && streakOpen && createPortal(<StreakSheet onClose={() => setStreakOpen(false)} />, document.body)}
    </header>
  );
}

export function BottomNav({ route }: { route: string }) {
  const lang = useStore((s) => s.lang);
  const items = [
    { href: "#/", on: route === "" || route.startsWith("match"), label: t("live", lang), icon: <LiveIcon /> },
    { href: "#/leagues", on: route === "leagues", label: t("leagues", lang), icon: <Trophy /> },
    { href: "#/cards", on: route === "cards", label: t("cards", lang), icon: <CardsIcon /> },
    { href: "#/me", on: route === "me", label: t("me", lang), icon: <UserIcon /> },
  ];
  return (
    <nav className="nav" aria-label="Main">
      {items.map((i) => (
        <a key={i.href} href={i.href} className={i.on ? "on" : undefined} aria-current={i.on ? "page" : undefined}>
          {i.icon}
          {i.label}
        </a>
      ))}
    </nav>
  );
}

export function Toasts() {
  const toasts = useStore((s) => s.toasts);
  const dismiss = useStore((s) => s.dismiss);
  const lang = useStore((s) => s.lang);
  const last = toasts[toasts.length - 1];

  useEffect(() => {
    if (!last) return;
    if (last.kind === "win" || last.kind === "sticker") {
      const css = getComputedStyle(document.documentElement);
      const gold = ["--gold", "--gold-2", "--silver", "--text"].map((v) => css.getPropertyValue(v).trim() || "#D8B26E");
      confetti({ particleCount: last.kind === "sticker" ? 140 : 80, spread: 70, origin: { y: 0.15 }, colors: gold, disableForReducedMotion: true });
      navigator.vibrate?.([20, 40, 20]);
    }
  }, [last?.id]);

  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.slice(-3).map((x) => (
        <div key={x.id} className={`toast ${x.kind}`} onClick={() => dismiss(x.id)}>
          {x.kind === "win" && (
            <div>
              <div className="big">{t("calledIt", lang).toUpperCase()}</div>
              <div className="sub">+{x.call.payout} {t("biscuits", lang)} · {x.call.question}</div>
            </div>
          )}
          {x.kind === "loss" && (
            <div>
              <div className="big" style={{ fontSize: 22 }}>{t("notThisTime", lang)}</div>
              <div className="sub">{x.call.question}{x.call.goldfish ? ` · ${t("stSaved", lang).split("·")[1]?.trim() ?? ""}` : ""}</div>
            </div>
          )}
          {x.kind === "sticker" && (
            <>
              <StickerBadge s={x.sticker} size={52} />
              <div>
                <div className="sub" style={{ letterSpacing: "0.08em", color: `var(--${x.sticker.tier === "gold" ? "gold" : x.sticker.tier === "silver" ? "silver" : "bronze"})` }}>
                  {t("newSticker", lang).toUpperCase()}
                </div>
                <div className="big" style={{ fontSize: 22 }}>{stickerText(x.sticker, lang).name}</div>
                <div className="sub">{x.sticker.detail || stickerText(x.sticker, lang).how}</div>
              </div>
            </>
          )}
          {x.kind === "hope" && (
            <div>
              <div className="big" style={{ fontSize: 20 }}>{t("hopeLine", lang)}</div>
              <div className="sub">{t("hopeSub", lang)} {Math.round(x.call.p * 100)}% · {x.call.question}</div>
            </div>
          )}
          {x.kind === "mission" && (
            <div>
              <div className="sub" style={{ color: "var(--gold-2)" }}>MISSION COMPLETE · +{x.reward}</div>
              <div style={{ fontWeight: 700 }}>{x.label}</div>
            </div>
          )}
          {x.kind === "goldfish" && (
            <>
              <span className="fishbadge"><Fish size={26} /></span>
              <div>
                <div className="sub" style={{ color: "var(--gold-2)", letterSpacing: "0.08em" }}>{t("goldfish", lang).toUpperCase()}!</div>
                <div style={{ fontWeight: 700 }}>{t("gfToast", lang).replace("{n}", String(x.streak))}</div>
              </div>
            </>
          )}
          {x.kind === "error" && <div style={{ fontWeight: 600 }}>{x.text}</div>}
        </div>
      ))}
    </div>
  );
}

/** What a streak is worth and how the Goldfish protects it. Opens from the streak pill. */
function StreakSheet({ onClose }: { onClose: () => void }) {
  const user = useStore((s) => s.user)!;
  const lang = useStore((s) => s.lang);
  const tiers = [
    { at: 3, x: "1.25x" },
    { at: 5, x: "1.5x" },
  ];
  return (
    <div className="sheet" role="dialog" aria-modal="true" aria-labelledby="streak-title" onClick={onClose}>
      <div className="sheet-inner" onClick={(e) => e.stopPropagation()}>
        <div className="row">
          <h2 id="streak-title" className="num" style={{ margin: 0, fontSize: 30 }}>{t("streakTitle", lang).toUpperCase()}</h2>
          <span className="pill gold"><Flame /> {user.streak}</span>
        </div>
        <p className="muted" style={{ margin: 0, lineHeight: 1.5 }}>{t("streakHow", lang)}</p>
        <div className="tiers">
          {tiers.map((tr) => (
            <div key={tr.at} className={`tier${user.streak >= tr.at ? " on" : ""}`}>
              <b>{tr.at}<small>{t("inARow", lang)}</small></b>
              <span>{tr.x}</span>
            </div>
          ))}
        </div>
        <div className={`gfcard${user.goldfish_available ? "" : " used"}`}>
          <span className="fishbadge"><Fish size={30} /></span>
          <div>
            <b>{user.goldfish_available ? t("gfReady", lang) : t("gfUsed", lang)}</b>
            <p>{t("gfHow", lang)}</p>
          </div>
        </div>
        <button className="cta" onClick={onClose}>{t("gotIt", lang)}</button>
      </div>
    </div>
  );
}
