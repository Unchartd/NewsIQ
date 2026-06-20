import { ImageResponse } from "next/og";
import { NextRequest } from "next/server";

export const runtime = "edge";

function IconSVG({ size }: { size: number }) {
  const radius = Math.round(size * 0.2);
  const fontSize = Math.round(size * 0.55);
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: radius,
        background: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "sans-serif",
        fontWeight: 900,
        fontSize,
        color: "#fff",
        letterSpacing: "-3px",
      }}
    >
      N
    </div>
  );
}

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ size?: string }> }
) {
  const { size: sizeParam } = await params;
  const size = sizeParam === "512" ? 512 : 192;
  return new ImageResponse(<IconSVG size={size} />, { width: size, height: size });
}
