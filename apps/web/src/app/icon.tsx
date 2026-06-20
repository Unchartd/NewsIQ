import { ImageResponse } from "next/og";

export const sizes = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: 8,
          background: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "sans-serif",
          fontWeight: 900,
          fontSize: 18,
          color: "#fff",
          letterSpacing: "-1px",
        }}
      >
        N
      </div>
    ),
    { width: 32, height: 32 }
  );
}
