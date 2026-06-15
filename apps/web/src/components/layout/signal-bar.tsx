"use client";

interface SignalBarProps {
  variant?: "pulse" | "progress";
  progress?: number;
  active?: boolean;
}

export function SignalBar({ active = false }: SignalBarProps) {
  if (!active) return <div className="sig" style={{ opacity: 0 }} />;
  return <div className="sig" />;
}
