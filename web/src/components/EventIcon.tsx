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

export function EventIcon({ kind, size = 18 }: { kind: EventKind; size?: number }) {
  const common = { width: size, height: size, viewBox: "0 0 24 24", "aria-hidden": true as const, className: `ev-icon ev-${kind}` };
  switch (kind) {
    case "goal": // a ball
      return (
        <svg {...common} fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinejoin="round">
          <circle cx="12" cy="12" r="9" />
          <path d="M12 8.2l3.3 2.4-1.3 3.9h-4l-1.3-3.9z" fill="currentColor" />
          <path d="M12 3v5.2M15.3 10.6l5-1.7M14 14.5l3.2 4.4M10 14.5l-3.2 4.4M8.7 10.6l-5-1.7" />
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
    case "kickoff": // a whistle
      return (
        <svg {...common} fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinejoin="round" strokeLinecap="round">
          <path d="M3 10h9l7-3v4.5a6 6 0 1 1-12 1.5" />
          <circle cx="11" cy="14.5" r="1.4" fill="currentColor" />
          <path d="M3 10v3" />
        </svg>
      );
    case "half_time": // a half-filled clock
      return (
        <svg {...common} fill="none" stroke="currentColor" strokeWidth={1.7}>
          <circle cx="12" cy="12" r="9" />
          <path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor" stroke="none" />
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
