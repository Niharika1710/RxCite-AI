"use client";

import Logo from "./logo";
import { useState } from "react";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validateEmail(value: string): string | null {
  if (!value.trim()) return "Email is required";
  if (!EMAIL_RE.test(value)) return "Enter a valid email address";
  return null;
}

function validatePassword(value: string): string | null {
  if (!value) return "Password is required";
  if (value.length < 8) return "Password must be at least 8 characters";
  return null;
}

export default function Login({ onLogin }: { onLogin: (name: string) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [touched, setTouched] = useState({ email: false, password: false });

  const emailError = validateEmail(email);
  const passwordError = validatePassword(password);
  const isValid = !emailError && !passwordError;

  const submit = () => {
    setTouched({ email: true, password: true });
    if (!isValid) return;
    // Demo login: accepts anything valid, derives a display name from the email.
    const name = email.trim() ? email.split("@")[0] : "there";
    const display = name.charAt(0).toUpperCase() + name.slice(1);
    onLogin(display);
  };

  const inputStyle = (hasError: boolean) => ({
    width: "100%",
    boxSizing: "border-box" as const,
    border: `1px solid ${hasError ? "#E5534B" : "#E8E8E8"}`,
    borderRadius: 11,
    padding: "10px 13px",
    fontSize: 13.5,
    color: "#1F1F1F",
    background: "#FCFCFC",
    outline: "none",
  });

  const errorStyle = { fontSize: 11, color: "#E5534B", margin: "5px 0 0" };

  return (
    <div style={{ minHeight: "100vh", background: "#D9D9DB", display: "flex", alignItems: "center", justifyContent: "center", padding: 20, fontFamily: "var(--app-font)" }}>
      <div style={{ position: "relative", width: "100%", maxWidth: 980, minHeight: 560, background: "#FAFAFA", borderRadius: 20, overflow: "hidden", boxShadow: "0 1px 3px rgba(0,0,0,.04), 0 12px 40px rgba(0,0,0,.08)", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ position: "absolute", top: -60, right: -30, width: 460, height: 340, background: "radial-gradient(circle at 65% 30%, rgba(120,160,235,.20), transparent 60%)", pointerEvents: "none" }} />
        <div style={{ position: "absolute", bottom: 50, left: 50, width: 140, height: 90, opacity: 0.4, pointerEvents: "none", backgroundImage: "radial-gradient(#D2D6DC 1px, transparent 1px)", backgroundSize: "12px 12px", WebkitMaskImage: "radial-gradient(circle, #000, transparent 72%)" }} />

        <div style={{ position: "relative", zIndex: 2, width: 340, background: "#FFFFFF", border: "1px solid #EDEDED", borderRadius: 18, padding: "34px 32px", boxShadow: "0 4px 24px rgba(0,0,0,.05)" }}>
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 26 }}>
            <Logo size={17} />
            </div>

          <p style={{ fontSize: 20, fontWeight: 600, color: "#1A1A1A", textAlign: "center", margin: "0 0 5px", letterSpacing: "-0.02em" }}>Welcome back</p>
          <p style={{ fontSize: 13, color: "#9A9A9A", textAlign: "center", margin: "0 0 24px", lineHeight: 1.5 }}>Sign in to continue to your workspace</p>

          <label style={{ display: "block", fontSize: 11.5, color: "#7A7A7A", margin: "0 0 6px", fontWeight: 500 }}>Email</label>
          <input value={email} onChange={(e) => setEmail(e.target.value)}
            onBlur={() => setTouched((t) => ({ ...t, email: true }))}
            placeholder="you@example.com"
            style={inputStyle(touched.email && !!emailError)} />
          {touched.email && emailError && <p style={errorStyle}>{emailError}</p>}

          <div style={{ marginBottom: 14 }} />

          <label style={{ display: "block", fontSize: 11.5, color: "#7A7A7A", margin: "0 0 6px", fontWeight: 500 }}>Password</label>
          <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" placeholder="••••••••"
            onBlur={() => setTouched((t) => ({ ...t, password: true }))}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            style={inputStyle(touched.password && !!passwordError)} />
          {touched.password && passwordError && <p style={errorStyle}>{passwordError}</p>}

          <div style={{ marginBottom: 20 }} />

          <button onClick={submit} disabled={!isValid}
            style={{ width: "100%", background: isValid ? "#151515" : "#B8B8B8", color: "#fff", border: "none", borderRadius: 11, padding: 12, fontSize: 13.5, fontWeight: 500, cursor: isValid ? "pointer" : "not-allowed", transition: "background .2s ease" }}
            onMouseEnter={(e) => { if (isValid) e.currentTarget.style.background = "#333"; }}
            onMouseLeave={(e) => { if (isValid) e.currentTarget.style.background = "#151515"; }}>
            Sign in
          </button>

          <p style={{ textAlign: "center", fontSize: 12, color: "#A5A5A5", margin: "14px 0 0" }}>
            Demo: any valid email + 8&#43; char password
          </p>

          <p style={{ textAlign: "center", fontSize: 12, color: "#A5A5A5", margin: "8px 0 0" }}>
            New here? <span style={{ color: "#151515", fontWeight: 500, cursor: "pointer" }}>Create account</span>
          </p>
        </div>
      </div>
    </div>
  );
}