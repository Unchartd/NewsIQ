"use client";

import { Zap } from "lucide-react";

interface BreakingBannerProps {
  text: string;
  time?: string;
  onClick?: () => void;
}

export function BreakingBanner({ text, time, onClick }: BreakingBannerProps) {
  return (
    <div className="bb-banner" onClick={onClick} style={{ cursor: onClick ? "pointer" : undefined }}>
      <Zap size={14} fill="currentColor" />
      <span className="bb-lbl">BREAKING</span>
      <span className="bb-txt">{text}</span>
      {time && <span className="bb-time">{time}</span>}
    </div>
  );
}
