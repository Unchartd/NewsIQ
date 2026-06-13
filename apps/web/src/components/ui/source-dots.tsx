"use client";

const SOURCE_COLORS = [
  "#1D4ED8", "#DC2626", "#16A34A", "#D97706", "#7C3AED",
  "#0E7490", "#065F46", "#374151", "#6B21A8", "#0369A1",
];

interface SourceDotsProps {
  count: number;
  max?: number;
}

export function SourceDots({ count, max = 5 }: SourceDotsProps) {
  const dotsToShow = Math.min(count, max);
  return (
    <div className="srcs">
      <div className="sdots">
        {Array.from({ length: dotsToShow }).map((_, i) => (
          <div
            key={i}
            className="sdot"
            style={{ background: SOURCE_COLORS[i % SOURCE_COLORS.length] }}
          />
        ))}
      </div>
      {count} source{count !== 1 ? "s" : ""}
    </div>
  );
}
