import { useEffect, useRef, useState } from "react";
import type { ClubRef } from "../types";

export function Crest({ club, round = false, size }: { club: ClubRef; round?: boolean; size?: "sm" }) {
  const light = isLight(club.primary);
  return (
    <div
      className={`crest${round ? " round" : ""}${size ? ` ${size}` : ""}`}
      style={{ background: club.primary, color: light ? "#1A0B20" : "#F4F1F6", border: `1px solid ${club.secondary}55` }}
      aria-label={club.name}
      role="img"
    >
      {club.monogram}
    </div>
  );
}

function isLight(hex: string) {
  const n = parseInt(hex.slice(1), 16);
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  return 0.299 * r + 0.587 * g + 0.114 * b > 150;
}

/** Number that briefly bumps when it changes. */
export function Animated({ value, format = (v: number) => v.toLocaleString("en-US") }: { value: number; format?: (v: number) => string }) {
  const [shown, setShown] = useState(value);
  const [bump, setBump] = useState(false);
  const prev = useRef(value);
  useEffect(() => {
    if (prev.current === value) return;
    const from = prev.current;
    prev.current = value;
    setBump(true);
    const start = performance.now();
    let raf = 0;
    const step = (now: number) => {
      const k = Math.min(1, (now - start) / 700);
      setShown(Math.round(from + (value - from) * (1 - Math.pow(1 - k, 3))));
      if (k < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    const tm = setTimeout(() => setBump(false), 600);
    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(tm);
    };
  }, [value]);
  return <span className={bump ? "bump" : undefined}>{format(shown)}</span>;
}

export const pct = (p: number) => `${Math.round(p * 100)}%`;
