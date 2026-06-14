"use client";

/* ─────────────────────────────────────────────────────────────────────────────
   SKELETONS
   All skeletons must mirror the exact DOM structure of the real components
   they stand in for.  Use the same CSS classes (.card, .cmeta, .chead,
   .csum, .cfoot) so dimensions are driven by the stylesheet, not inline
   values — this eliminates the "jump" when real data replaces the placeholder.
───────────────────────────────────────────────────────────────────────────── */

/** Pulsing placeholder bar */
function Bar({ w = "100%", h = 14, r = 4, mb = 0 }: { w?: string | number; h?: number; r?: number; mb?: number }) {
  return (
    <div
      className="sk-bar"
      style={{
        width: w,
        height: h,
        borderRadius: r,
        marginBottom: mb || undefined,
        flexShrink: 0,
      }}
    />
  );
}

/** Pulsing placeholder circle */
function Circle({ size = 20 }: { size?: number }) {
  return (
    <div
      className="sk-bar"
      style={{ width: size, height: size, borderRadius: "50%", flexShrink: 0 }}
    />
  );
}

export function StoryCardSkeleton() {
  return (
    /* Use the identical .card class so CSS drives all box-model dimensions */
    <div className="card" style={{ cursor: "default", pointerEvents: "none" }}>
      {/* Meta row — mirrors .cmeta */}
      <div className="cmeta">
        <Bar w={60} h={18} r={99} />      {/* category badge */}
        <span className="mdot" />
        <Bar w={80} h={13} />              {/* location */}
        <span className="mtime" style={{ marginLeft: "auto" }}>
          <Bar w={48} h={13} />
        </span>
      </div>

      {/* Headline — mirrors .chead (2 lines clamped) */}
      <div className="chead" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <Bar h={19} />
        <Bar w="72%" h={19} />
      </div>

      {/* Summary — mirrors .csum (3 lines clamped) */}
      <div className="csum" style={{ display: "flex", flexDirection: "column", gap: 7 }}>
        <Bar h={14} />
        <Bar h={14} />
        <Bar w="83%" h={14} />
      </div>

      {/* Footer — mirrors .cfoot */}
      <div className="cfoot">
        <div className="srcs">
          <Bar w={80} h={13} />
        </div>
        <div className="bkbtn" style={{ marginLeft: "auto", cursor: "default" }}>
          <Circle size={32} />
        </div>
      </div>
    </div>
  );
}

export function StoryFeedSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="feed-list">
      {Array.from({ length: count }).map((_, i) => (
        <StoryCardSkeleton key={i} />
      ))}
    </div>
  );
}

// Legacy export kept for any pages that import it
export { StoryFeedSkeleton as TrendingBannerSkeleton };
