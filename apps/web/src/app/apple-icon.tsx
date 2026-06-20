import { ImageResponse } from "next/og";

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
          background: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "sans-serif",
          fontWeight: 900,
          fontSize: 100,
          color: "#fff",
          letterSpacing: "-4px",
        }}
      >
        N
      </div>
    ),
    { width: 180, height: 180 }
  );
}
