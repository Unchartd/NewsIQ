import { ImageResponse } from "next/og";
import { brandColors } from "@/branding/colors";

export const sizes = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: 7,
          background: brandColors.primary,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          position: "relative",
        }}
      >
        {/* Lightning bolt + N rendered as text shorthand for OG ImageResponse */}
        <svg
          viewBox="0 0 64 64"
          width="22"
          height="22"
          fill="none"
        >
          <path d="M38 2L14 34h14l-6 28L46 30H32l6-28z" fill="#FFFFFF" />
          <path d="M24 28h4l4 8V28h4v16h-4l-4-8v8h-4V28z" fill={brandColors.primary} />
        </svg>
      </div>
    ),
    { width: 32, height: 32 }
  );
}
