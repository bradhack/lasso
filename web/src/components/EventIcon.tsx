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

// The ball's geometry, worked out once: a patch in the middle, a spoke from each of its corners to a patch on
// the rim, and seams from those patches out to the edge (the white panels between are hexagons).
const pt = (r: number, deg: number): [number, number] => {
  const a = (deg * Math.PI) / 180;
  return [12 + r * Math.cos(a), 12 + r * Math.sin(a)];
};
const at = ([x, y]: [number, number]) => `${x.toFixed(2)} ${y.toFixed(2)}`;
const poly = (ps: [number, number][]) => `M${ps.map(at).join("L")}Z`;
const BALL = (() => {
  const inner = 3.7; // the middle patch
  const spoke = 5.5; // where a spoke meets a rim patch
  const rimR = 3.3; // the rim patches
  const corners = [0, 1, 2, 3, 4].map((k) => -90 + 72 * k);
  let patches = poly(corners.map((d) => pt(inner, d)));
  let seams = patches;
  for (const d of corners) {
    const tip = pt(spoke, d);
    // A rim patch: a pentagon pointing at the middle, its center further out along the same line.
    const c = pt(spoke + rimR, d);
    const verts = [0, 1, 2, 3, 4].map((k) => {
      const a = ((d + 180 + 72 * k) * Math.PI) / 180;
      return [c[0] + rimR * Math.cos(a), c[1] + rimR * Math.sin(a)] as [number, number];
    });
    patches += poly(verts);
    seams += `${poly(verts)}M${at(pt(inner, d))}L${at(tip)}`;
    // From the patch's two side corners, a seam straight out to the rim.
    for (const v of [verts[1], verts[4]]) {
      const len = Math.hypot(v[0] - 12, v[1] - 12);
      const out: [number, number] = [12 + ((v[0] - 12) / len) * 10, 12 + ((v[1] - 12) / len) * 10];
      seams += `M${at(v)}L${at(out)}`;
    }
  }
  return { patches, seams };
})();

export function EventIcon({ kind, size = 18 }: { kind: EventKind; size?: number }) {
  const clip = `ball-${useId().replace(/:/g, "")}`;
  const common = { width: size, height: size, viewBox: "0 0 24 24", "aria-hidden": true as const, className: `ev-icon ev-${kind}` };
  switch (kind) {
    case "goal": // a football: tinted patches, white panels between them, seams running out to the rim
      return (
        <svg {...common} fill="none" stroke="currentColor" strokeWidth={1.3} strokeLinejoin="round" strokeLinecap="round">
          <defs><clipPath id={clip}><circle cx="12" cy="12" r="9.2" /></clipPath></defs>
          <g clipPath={`url(#${clip})`}>
            <path d={BALL.patches} fill="currentColor" fillOpacity={0.35} />
            <path d={BALL.seams} />
          </g>
          <circle cx="12" cy="12" r="9.2" strokeWidth={1.8} />
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
    case "kickoff": // the start: a play button
      return (
        <svg {...common} fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinejoin="round">
          <circle cx="12" cy="12" r="9" />
          <path d="M10 8.3l5.6 3.7-5.6 3.7z" fill="currentColor" />
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
