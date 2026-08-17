"use client";

import { Zap } from "lucide-react";
import { activateOnKey } from "@/lib/a11y";

interface BreakingBannerProps {
  text: string;
  time?: string;
  onClick?: () => void;
}

export function BreakingBanner({ text, time, onClick }: BreakingBannerProps) {
  return (
    <div className="bb-banner" onClick={onClick} style={{ cursor: onClick ? "pointer" : undefined }} role="button" tabIndex={0} onKeyDown={activateOnKey(onClick)}>
      <Zap size={14} fill="currentColor" />
      <span className="bb-lbl">BREAKING</span>
      <span className="bb-txt">{text}</span>
      {time && <span className="bb-time">{time}</span>}
    </div>
  );
}
