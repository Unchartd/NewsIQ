"use client";

interface SignalBarProps {
  variant?: "pulse" | "progress";
  progress?: number;
}

export function SignalBar({ variant = "pulse", progress = 65 }: SignalBarProps) {
  return (
    <div
      className={`signal-bar ${variant === "progress" ? "progress" : ""}`}
      style={variant === "progress" ? { "--progress": `${progress}%` } as React.CSSProperties : undefined}
    />
  );
}
