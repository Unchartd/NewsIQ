"use client";

import React from "react";

interface SignalBarProps {
  variant?: "pulse" | "progress";
  progress?: number;
  active?: boolean;
}

export function SignalBar({
  variant = "pulse",
  progress = 0,
  active = false,
}: SignalBarProps) {
  const classes = [
    "signal-bar",
    active ? "active" : "",
    variant === "progress" ? "progress" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const inlineStyles = {
    "--progress": `${progress}%`,
  } as React.CSSProperties;

  return <div className={classes} style={inlineStyles} />;
}
