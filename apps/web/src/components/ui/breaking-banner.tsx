"use client";

import { Zap } from "lucide-react";

interface BreakingBannerProps {
  text: string;
  time?: string;
  onClick?: () => void;
}

export function BreakingBanner({ text, time, onClick }: BreakingBannerProps) {
  return (
    <div className="niq-breaking-banner" onClick={onClick} style={{ cursor: onClick ? "pointer" : undefined }}>
      <Zap size={14} fill="currentColor" />
      <span className="niq-breaking-label">BREAKING</span>
      <span className="niq-breaking-text">{text}</span>
      {time && <span className="niq-breaking-time">{time}</span>}
    </div>
  );
}
