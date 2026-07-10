import { ImageResponse } from "next/og";
import { brandColors } from "@/branding/colors";

export const sizes = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: 180,
          height: 180,
          borderRadius: 38,
          background: brandColors.primary,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          position: "relative",
        }}
      >
        <svg
          viewBox="0 0 64 64"
          width="120"
          height="120"
          fill="none"
        >
          <path d="M38 2L14 34h14l-6 28L46 30H32l6-28z" fill="#FFFFFF" />
          <path d="M24 28h4l4 8V28h4v16h-4l-4-8v8h-4V28z" fill={brandColors.primary} />
        </svg>
      </div>
    ),
    { width: 180, height: 180 }
  );
}
