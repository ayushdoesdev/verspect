import { ImageResponse } from "next/og";

export const alt = "Verspect — Dependency intelligence for GitHub repositories";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function TwitterImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "76px 84px",
          backgroundColor: "#070b12",
          backgroundImage:
            "radial-gradient(ellipse at 75% 20%, rgba(61,214,198,.18), transparent 45%), linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px), linear-gradient(90deg,rgba(255,255,255,.035) 1px,transparent 1px)",
          backgroundSize: "auto, 48px 48px, 48px 48px",
          color: "#e8eef6",
          fontFamily: "Arial, sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 15,
            color: "#ffffff",
            fontSize: 27,
            fontWeight: 700,
          }}
        >
          <div
            style={{
              width: 43,
              height: 43,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              border: "1px solid #24544f",
              borderRadius: 13,
              background: "#10201f",
            }}
          >
            <svg width="25" height="25" viewBox="0 0 32 32" fill="none">
              <path
                d="M3 16h7l4 12 6-24 4 12h5"
                stroke="#3DD6C6"
                strokeWidth="2.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          Verspect
        </div>
        <div
          style={{
            display: "flex",
            marginTop: 57,
            color: "#88ddd4",
            fontSize: 16,
            letterSpacing: 4,
            textTransform: "uppercase",
          }}
        >
          Dependency intelligence
        </div>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            maxWidth: 990,
            marginTop: 20,
            fontSize: 62,
            fontWeight: 700,
            lineHeight: 1.11,
            letterSpacing: -2.5,
          }}
        >
          <span>Know your dependencies.</span>
          <span>Understand your risks.</span>
          <span style={{ color: "#3dd6c6" }}>Upgrade with confidence.</span>
        </div>
        <div
          style={{
            display: "flex",
            marginTop: 31,
            color: "#97a6b6",
            fontSize: 21,
          }}
        >
          Evidence-led analysis · self-hosted · open source
        </div>
      </div>
    ),
    { ...size },
  );
}
