import { useId } from "react";

/** One small icon per kind of match moment or event, for the timeline and banners. Decorative: the text next to
 * it always says what happened, so the icons are hidden from screen readers. */

export type EventKind =
  | "goal" | "red_card" | "yellow_card" | "var" | "kickoff" | "half_time" | "full_time" | "swing" | "pulse"
  | "chance" | "substitution";

/** Which icon a story trigger or a feed event type gets. */
export function kindOf(type: string): EventKind {
  switch (type) {
    case "goal": return "goal";
    case "red_card": return "red_card";
    case "yellow_card": return "yellow_card";
    case "var_overturned": case "var_check": case "var_decision": return "var";
    case "kickoff": return "kickoff";
    case "half_time": return "half_time";
    case "full_time": return "full_time";
    case "swing": case "swing_draw": return "swing";
    case "shot": return "chance";
    case "substitution": return "substitution";
    default: return "pulse";
  }
}

// The ball's geometry, worked out once: a pentagon in the middle, spokes to five more around it.
const pent = (cx: number, cy: number, r: number, rot: number) =>
  `M${[0, 1, 2, 3, 4].map((k) => {
    const a = ((rot + 72 * k) * Math.PI) / 180;
    return `${(cx + r * Math.cos(a)).toFixed(2)} ${(cy + r * Math.sin(a)).toFixed(2)}`;
  }).join("L")}Z`;
const BALL = (() => {
  const r = 3.1; // the patches' size
  const out = 8.9; // how far out the rim patches sit (the rim cuts them)
  const center = pent(12, 12, r, -90);
  const rim: string[] = [];
  const seams: string[] = [];
  for (let k = 0; k < 5; k++) {
    const a = ((-90 + 72 * k) * Math.PI) / 180;
    const [c, s_] = [Math.cos(a), Math.sin(a)];
    rim.push(pent(12 + out * c, 12 + out * s_, r, -90 + 72 * k + 180));
    seams.push(`M${(12 + r * c).toFixed(2)} ${(12 + r * s_).toFixed(2)}L${(12 + (out - r) * c).toFixed(2)} ${(12 + (out - r) * s_).toFixed(2)}`);
  }
  return { center, rim, seams };
})();

export function EventIcon({ kind, size = 18 }: { kind: EventKind; size?: number }) {
  const clip = `ball-${useId().replace(/:/g, "")}`;
  const common = { width: size, height: size, viewBox: "0 0 24 24", "aria-hidden": true as const, className: `ev-icon ev-${kind}` };
  switch (kind) {
    case "goal": // a football: a black patch in the middle, five more cut off by the rim
      return (
        <svg {...common}>
          <defs><clipPath id={clip}><circle cx="12" cy="12" r="9" /></clipPath></defs>
          <g clipPath={`url(#${clip})`} fill="currentColor">
            <path d={BALL.center} />
            {BALL.rim.map((d, i) => <path key={i} d={d} />)}
          </g>
          <g stroke="currentColor" strokeWidth={1.3} strokeLinecap="round">
            {BALL.seams.map((d, i) => <path key={i} d={d} />)}
          </g>
          <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth={1.7} />
        </svg>
      );
    case "red_card":
    case "yellow_card": // a card
      return (
        <svg {...common}>
          <rect x="7" y="3.5" width="10" height="15" rx="1.8" transform="rotate(12 12 11)"
            fill={kind === "red_card" ? "var(--live)" : "#F5C842"} />
        </svg>
      );
    case "var": // a review screen
      return (
        <svg {...common} fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinejoin="round" strokeLinecap="round">
          <rect x="3" y="4.5" width="18" height="12" rx="2" />
          <path d="M10.5 8l4 2.5-4 2.5z" fill="currentColor" />
          <path d="M9 20h6M12 16.5V20" />
        </svg>
      );
    case "kickoff": // a referee's whistle: round body, mouthpiece out to the right with its air slot, the pea inside
      return (
        <svg {...common} fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinejoin="round" strokeLinecap="round">
          <path d="M9 8.5H21.5V13H14.8" />
          <path d="M15.2 8.5V10.6H18V8.5" />
          <circle cx="9" cy="14.5" r="6" />
          <circle cx="9" cy="14.5" r="1.9" fill="currentColor" stroke="none" />
        </svg>
      );
    case "half_time": // the break: a pause sign in a circle
      return (
        <svg {...common} fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round">
          <circle cx="12" cy="12" r="9" />
          <path d="M10 8.5v7M14 8.5v7" strokeWidth={2.2} />
        </svg>
      );
    case "full_time": // a checkered flag
      return (
        <svg {...common} fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinejoin="round">
          <path d="M5 21V3.5" strokeLinecap="round" />
          <path d="M5 4h14v9H5z" />
          <path d="M5 4h3.5v3H5zM12 4h3.5v3H12zM8.5 7H12v3H8.5zM15.5 7H19v3h-3.5zM5 10h3.5v3H5zM12 10h3.5v3H12z" fill="currentColor" stroke="none" />
        </svg>
      );
    case "swing": // a line that turns
      return (
        <svg {...common} fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinejoin="round" strokeLinecap="round">
          <path d="M3 17l5-5 4 3 8-8" />
          <path d="M15 7h5v5" />
        </svg>
      );
    case "chance": // a target
      return (
        <svg {...common} fill="none" stroke="currentColor" strokeWidth={1.7}>
          <circle cx="12" cy="12" r="8" />
          <circle cx="12" cy="12" r="3.5" />
          <circle cx="12" cy="12" r="0.8" fill="currentColor" />
        </svg>
      );
    case "substitution": // in and out
      return (
        <svg {...common} fill="none" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round">
          <path d="M8 20V6M4.5 9.5L8 6l3.5 3.5" stroke="var(--ok, #3FB27F)" />
          <path d="M16 4v14M12.5 14.5L16 18l3.5-3.5" stroke="var(--live)" />
        </svg>
      );
    default: // an update: a clock
      return (
        <svg {...common} fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round">
          <circle cx="12" cy="12" r="9" />
          <path d="M12 7v5l3.5 2" />
        </svg>
      );
  }
}
