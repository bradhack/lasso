import type { ReactElement } from "react";
import type { Lang, Sticker } from "../types";

/** One sticker: a die-cut badge with a tier ring and a simple line icon. Unearned ones show as outlines. */
export function StickerBadge({ s, size = 72 }: { s: Pick<Sticker, "id" | "tier" | "earned">; size?: number }) {
  return (
    <svg className={`sticker-art ${s.tier}${s.earned ? "" : " locked"}`} width={size} height={size} viewBox="0 0 72 72" aria-hidden="true">
      <circle cx="36" cy="36" r="33" className="ring" />
      <circle cx="36" cy="36" r="27" className="face" />
      <g transform="translate(24 24)" className="glyph">{ICONS[s.id] ?? ICONS.called_it}</g>
    </svg>
  );
}

export function stickerText(s: { name: Record<string, string>; how: Record<string, string> }, lang: Lang) {
  return { name: s.name[lang] ?? s.name.en, how: s.how[lang] ?? s.how.en };
}

const ICONS: Record<string, ReactElement> = {
  first_call: <path d="M5 19l2-6 9-9 4 4-9 9zM14 6l4 4" />,
  called_it: <path d="M4 12.5l5 5L20 6" />,
  believe: (
    <>
      <rect x="2.5" y="6" width="19" height="12" rx="1.5" />
      <path d="M1 7.5l4-2.5M23 7.5l-4-2.5M7 12h10" />
    </>
  ),
  halftime_tea: <path d="M4 9h12v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5zM16 10.5h1.5a2.5 2.5 0 0 1 0 5H16M8 3.5c0 1.5 1.5 1.5 1.5 3M12 3.5c0 1.5 1.5 1.5 1.5 3" />,
  polyglot: <path d="M3 5h11v8H8l-3 3v-3H3zM10 15v2h6l3 3v-3h2V9h-5" />,
  underdog: <path d="M12 20s-7-4.3-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.7-7 10-7 10z" />,
  hat_trick: (
    <>
      <circle cx="6" cy="15" r="3.4" />
      <circle cx="12" cy="8" r="3.4" />
      <circle cx="18" cy="15" r="3.4" />
    </>
  ),
  on_fire: <path d="M12 3c1 3.2 4.5 4.8 4.5 9a4.5 4.5 0 0 1-9 0c0-2.2 1.2-3.4 2.2-4.3 0 2 .9 3 2 3 0-3-1.1-5 .3-7.7z" />,
  rom_com: <path d="M12 20s-8-4.8-8-10.5A4.3 4.3 0 0 1 12 7a4.3 4.3 0 0 1 8 2.5C20 15.2 12 20 12 20zM8.5 11.5l2 2 4-4" />,
  goldfish: <path d="M3 12c3-5 9-6 13-2l5-3-1.5 5L21 17l-5-3c-4 4-10 3-13-2zM8.5 11v.01" />,
  sharp_eye: (
    <>
      <path d="M2 12s3.5-6.5 10-6.5S22 12 22 12s-3.5 6.5-10 6.5S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  long_shot: <path d="M4 20L20 4M14 4h6v6M4 14l3 3M7 11l3 3" />,
  ten_men: <path d="M5 7l2.5-1.5V18M12.5 9a3.5 3.5 0 0 1 7 0v6a3.5 3.5 0 0 1-7 0z" />,
  comeback: <path d="M4 15a8 8 0 0 0 15.5 1M20 9A8 8 0 0 0 4.5 8M4 4v4.5h4.5M20 20v-4.5h-4.5" />,
  bullseye: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="4.5" />
      <circle cx="12" cy="12" r="0.8" />
    </>
  ),
  unstoppable: <path d="M13 2L5 13.5h6L10 22l9-12.5h-6z" />,
  press_pass: <path d="M12 3a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3zM6 11a6 6 0 0 0 12 0M12 17v4M9 21h6" />,
  all_ears: <path d="M4 16v-4a8 8 0 0 1 16 0v4M4 15h3.5v6H4zM16.5 15H20v6h-3.5z" />,
  var_whisperer: <path d="M3 4h18v12H3zM8 21h8M12 16v5M10 7.5l5 2.5-5 2.5z" />,
  gaffers_eye: <path d="M12 3l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.4l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z" />,
  on_the_up: <path d="M3 18l6-6 4 4 8-8M15 8h6v6" />,
  saw_it_coming: <path d="M12 3a7 7 0 1 1 0 14 7 7 0 0 1 0-14zM6.5 21h11M9 17l-1.5 4M15 17l1.5 4M9 9.5a3.5 3.5 0 0 1 3-3" />,
  diamond_dog: <path d="M6 4h12l3.5 5L12 21 2.5 9zM2.5 9h19M9 4l-1.5 5L12 21M15 4l1.5 5L12 21" />,
};
