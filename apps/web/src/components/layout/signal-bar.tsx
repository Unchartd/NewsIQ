"use client";

interface SignalBarProps {
  variant?: "pulse" | "progress";
  progress?: number;
  active?: boolean;
}

export function SignalBar({ variant = "pulse", progress = 65, active = false }: SignalBarProps) {
  return (
    <div
      className={`signal-bar ${variant === "progress" ? "progress" : ""} ${active ? "active" : ""}`}
      style={variant === "progress" ? { "--progress": `${progress}%` } as React.CSSProperties : undefined}
    />
  );
}
