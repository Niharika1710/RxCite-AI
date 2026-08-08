"use client";

import { ShieldCheck } from "lucide-react";

// Change BRAND_NAME here to rename everywhere at once.
export const BRAND_NAME = "RxCite";
export const BRAND_SUFFIX = "AI";

export default function Logo({ size = 20, showText = true, dark = false }: { size?: number; showText?: boolean; dark?: boolean }) {
  const box = Math.round(size * 1.5);
  const badgeBg = dark ? "#E4E7EB" : "#151515";
  const shieldColor = dark ? "#121519" : "#fff";
  const textColor = dark ? "#F2F4F7" : "#151515";
  const suffixColor = dark ? "#7A8290" : "#9A988F";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <span
        className="logo-badge"
        style={{
          width: box,
          height: box,
          borderRadius: box * 0.28,
          background: badgeBg,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        <ShieldCheck size={size} color={shieldColor} strokeWidth={2.2} />
      </span>
      {showText && (
        <span style={{ fontSize: size, fontWeight: 600, color: textColor, letterSpacing: "-0.02em", whiteSpace: "nowrap" }}>
          {BRAND_NAME} <span style={{ color: suffixColor, fontWeight: 500 }}>{BRAND_SUFFIX}</span>
        </span>
      )}
    </div>
  );
}
export function LogoMark({ size = 16, animate = false }: { size?: number; animate?: boolean }) {
  const box = Math.round(size * 1.6);
  return (
    <span
      className={animate ? "mark-generating" : ""}
      style={{
        width: box, height: box, borderRadius: box * 0.28, background: "#EAF0FA",
        display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
      }}
    >
      <ShieldCheck size={size} color="#5B8DB8" strokeWidth={2.2} />
    </span>
  );
}