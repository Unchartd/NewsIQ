import { ImageResponse } from "next/og";
import { NextRequest } from "next/server";

export const runtime = "edge";

function BrandIcon({ size }: { size: number }) {
  const radius = Math.round(size * 0.22);
  const iconSize = Math.round(size * 0.7);
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: radius,
        background: "#EF4444",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        position: "relative",
      }}
    >
      <svg
        viewBox="0 0 64 64"
        width={iconSize}
        height={iconSize}
        fill="none"
      >
        <path d="M38 2L14 34h14l-6 28L46 30H32l6-28z" fill="#FFFFFF" />
        <path d="M24 28h4l4 8V28h4v16h-4l-4-8v8h-4V28z" fill="#EF4444" />
      </svg>
    </div>
  );
}

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ size?: string }> }
) {
  const { size: sizeParam } = await params;
  const size = sizeParam === "512" ? 512 : 192;
  return new ImageResponse(<BrandIcon size={size} />, { width: size, height: size });
}
