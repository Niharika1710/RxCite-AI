"use client";

import { useState, useRef, useEffect } from "react";
import { PanelLeftClose, PanelLeft, ArrowUp, ChevronDown, Plus, ImagePlus, X, Sun, Moon } from "lucide-react";
import Logo, { LogoMark } from "./logo";
import Login from "./login";

const API_URL = "http://127.0.0.1:8000/api/query";
const IMAGE_API_URL = "http://127.0.0.1:8000/api/query-image";
const STORAGE_KEY = "rxcite_history";

const DOMAINS = [
  { id: "pharma",   label: "Pharmaceutical", source: "FDA drug labels",         available: true,  dot: "#5B8DB8" },
  { id: "ayurveda", label: "Ayurveda",       source: "Coming soon",              available: false, dot: "#7BB89A" },
  { id: "home",     label: "Home remedies",  source: "Coming soon",              available: false, dot: "#E0B060" },
];

const STAGES = ["Routing query", "Retrieving evidence", "Validating citations", "Scoring confidence", "Safety gate"];

// ---- Theme system -------------------------------------------------------
// Two palettes. Semantic colors (confidence ring green/amber/red, domain dots)
// live OUTSIDE the palette and stay constant across themes — only surfaces,
// text, and borders flip. "light" preserves the original warm-minimal look;
// "dark" is a cool/clinical slate.
const THEMES = {
  light: {
    appBg: "#D9D9DB",
    shell: "#FAFAFA",
    sidebar: "#FFFFFF",
    sidebarBorder: "#EFEFEF",
    card: "#fff",
    cardBorder: "#ECECEC",
    inputBar: "#fff",
    inputBorder: "#E0E0E0",
    divider: "#EEE",
    dividerSoft: "#F0F0F0",
    textStrong: "#1A1A1A",
    text: "#1F1F1F",
    textMid: "#4A4A4A",
    textSoft: "#8E8E8E",
    textFaint: "#A5A5A5",
    textFainter: "#B5B5B5",
    textGhost: "#BDBDBD",
    avatarBg: "#E8ECF2",
    avatarText: "#6B7686",
    newBtnBorder: "#EAEAEA",
    histActive: "#F3F3F3",
    citeText: "#6E6E6E",
    citeHoverBorder: "#C9D4E4",
    citeHoverBg: "#F7F9FC",
    citeArrow: "#9AABC4",
    chip: "#F5F6F8",
    chipBorder: "#ECEDF0",
    chipText: "#4A515C",
    chevron: "#B6BCC6",
    menu: "#fff",
    menuBorder: "#EAEAEA",
    menuActive: "#F5F6F8",
    sendBg: "#151515",
    sendIcon: "#fff",
    sendDisabledBg: "#EDEDED",
    sendDisabledIcon: "#B5B5B5",
    attachActiveBg: "#EAF0F7",
    attachActiveIcon: "#4A6C93",
    attachIcon: "#9A9A9A",
    ringTrack: "#ECECEC",
    recBg: "#FBF4E6",
    recBorder: "#F0E2C0",
    recLabel: "#B08A3A",
    recText: "#8A5B0B",
    errBg: "#FBEBE7",
    errBorder: "#F0D2C7",
    errLabel: "#B5643E",
    errText: "#9E3B1B",
    glow: "rgba(120,160,235,.16)",
    shellShadow: "0 1px 3px rgba(0,0,0,.04), 0 8px 30px rgba(0,0,0,.06)",
  },
  dark: {
    appBg: "#0B0D10",
    shell: "#121519",
    sidebar: "#15181D",
    sidebarBorder: "#22262D",
    card: "#1A1E24",
    cardBorder: "#2A2F37",
    inputBar: "#1A1E24",
    inputBorder: "#2E343D",
    divider: "#2A2F37",
    dividerSoft: "#20242A",
    textStrong: "#F2F4F7",
    text: "#E4E7EB",
    textMid: "#C4C9D0",
    textSoft: "#8B929C",
    textFaint: "#6B717B",
    textFainter: "#565C66",
    textGhost: "#4A4F58",
    avatarBg: "#242A33",
    avatarText: "#9AA6B4",
    newBtnBorder: "#2A2F37",
    histActive: "#22262D",
    citeText: "#A6ADB6",
    citeHoverBorder: "#3D556E",
    citeHoverBg: "#1E2530",
    citeArrow: "#6E86A8",
    chip: "#222831",
    chipBorder: "#2E343D",
    chipText: "#AEB6C0",
    chevron: "#6B717B",
    menu: "#1A1E24",
    menuBorder: "#2A2F37",
    menuActive: "#242A33",
    sendBg: "#E4E7EB",
    sendIcon: "#121519",
    sendDisabledBg: "#242A33",
    sendDisabledIcon: "#565C66",
    attachActiveBg: "#1E2A3A",
    attachActiveIcon: "#7BA3D0",
    attachIcon: "#6B717B",
    ringTrack: "#2A2F37",
    recBg: "#211E14",
    recBorder: "#3A331E",
    recLabel: "#C7A24E",
    recText: "#D9B96A",
    errBg: "#2A1712",
    errBorder: "#4A2419",
    errLabel: "#D6785A",
    errText: "#E89A7E",
    glow: "rgba(90,130,210,.10)",
    shellShadow: "0 1px 3px rgba(0,0,0,.3), 0 8px 30px rgba(0,0,0,.4)",
  },
} as const;

type ThemeKey = keyof typeof THEMES;
type Theme = typeof THEMES["light"];

// A turn in the active conversation.
// kind "user"     -> something the person typed
// kind "question" -> a triage follow-up from the assistant (NO confidence ring)
// kind "answer"   -> a final evidence-grounded answer (ring + citations)
type Turn =
  | { kind: "user"; text: string }
  | { kind: "question"; text: string }
  | { kind: "answer"; data: any };

function ConfidenceRing({ level, theme }: { level: string; theme: Theme }) {
  const score = level === "High" ? 94 : level === "Medium" ? 62 : 28;
  const color = level === "High" ? "#3E9E6B" : level === "Medium" ? "#D98A2B" : "#D65440";
  const r = 15, c = 2 * Math.PI * r;
  const [off, setOff] = useState(c);
  useEffect(() => {
    const t = setTimeout(() => setOff(c * (1 - score / 100)), 150);
    return () => clearTimeout(t);
  }, [c, score]);
  return (
    <div style={{ position: "relative", width: 40, height: 40, flexShrink: 0 }}>
      <svg width="40" height="40" viewBox="0 0 40 40" style={{ transform: "rotate(-90deg)" }}>
        <circle cx="20" cy="20" r={r} fill="none" stroke={theme.ringTrack} strokeWidth="3.5" />
        <circle cx="20" cy="20" r={r} fill="none" stroke={color} strokeWidth="3.5" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={off} style={{ transition: "stroke-dashoffset 1s cubic-bezier(.22,1,.36,1)" }} />
      </svg>
      <span style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 600, color }}>
        {score}
      </span>
    </div>
  );
}

function AnswerTurn({ data, theme }: { data: any; theme: Theme }) {
  const words: string[] = data?.answer?.split(" ") ?? [];
  const [revealed, setRevealed] = useState(0);

  useEffect(() => {
    setRevealed(0);
    const t = setInterval(() => setRevealed((r) => (r >= words.length ? (clearInterval(t), r) : r + 2)), 28);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  const done = revealed >= words.length;

  return (
    <div style={{ display: "flex", gap: 12, margin: "8px 0 22px" }} className="fade-up">
      <LogoMark size={16} animate={!done} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontSize: 14.5, lineHeight: 1.75, color: theme.text, margin: 0 }}>
          {words.map((w, i) => (
            <span key={i} style={{ opacity: i < revealed ? 1 : 0, transition: "opacity .25s ease" }}>{w} </span>
          ))}
        </p>

        {done && (
          <div style={{ marginTop: 18, display: "flex", alignItems: "center", gap: 16 }} className="fade-up">
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <ConfidenceRing level={data.confidence_level} theme={theme} />
              <div>
                <p style={{ fontSize: 12.5, color: theme.text, margin: 0, fontWeight: 500 }}>{data.confidence_level} confidence</p>
                <p style={{ fontSize: 11, color: theme.textFaint, margin: "1px 0 0" }}>{data.is_refusal ? "Safety gate blocked" : "Safety gate passed"}</p>
              </div>
            </div>
            {data.citations?.length > 0 && (
              <>
                <span style={{ width: 1, height: 32, background: theme.divider }} />
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", flex: 1 }}>
                  {data.citations.map((c: any, i: number) => (
                    <a
                      key={i}
                      href={c.url || undefined}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        background: theme.card, border: `1px solid ${theme.cardBorder}`, borderRadius: 8,
                        padding: "5px 9px", fontSize: 10.5, color: theme.citeText,
                        textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 5,
                        cursor: c.url ? "pointer" : "default", transition: "all .15s ease",
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.borderColor = theme.citeHoverBorder; e.currentTarget.style.background = theme.citeHoverBg; }}
                      onMouseLeave={(e) => { e.currentTarget.style.borderColor = theme.cardBorder; e.currentTarget.style.background = theme.card; }}
                    >
                      <b style={{ fontWeight: 500, color: theme.text, textTransform: "capitalize" }}>{c.drug}</b>
                      <span>· {c.section.replace(/_/g, " ")}</span>
                      <span style={{ color: theme.citeArrow, fontSize: 11 }}>↗</span>
                    </a>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {data.recommendation && done && (
          <div style={{ marginTop: 14, background: theme.recBg, border: `1px solid ${theme.recBorder}`, borderRadius: 12, padding: "12px 15px" }} className="fade-up">
            <p style={{ fontSize: 10, color: theme.recLabel, letterSpacing: ".08em", textTransform: "uppercase", margin: "0 0 5px" }}>What to do instead</p>
            <p style={{ fontSize: 13, color: theme.recText, margin: 0, lineHeight: 1.55 }}>{data.recommendation}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function Home() {
  const [user, setUser] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [domainId, setDomainId] = useState("pharma");
  const [menuOpen, setMenuOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);

  // --- theme (persisted) ---
  const [themeKey, setThemeKey] = useState<ThemeKey>("light");
  const theme = THEMES[themeKey];
  useEffect(() => {
    try { const t = localStorage.getItem("rxcite_theme"); if (t === "dark" || t === "light") setThemeKey(t); } catch {}
  }, []);
  const toggleTheme = () => {
    setThemeKey((k) => {
      const next = k === "light" ? "dark" : "light";
      try { localStorage.setItem("rxcite_theme", next); } catch {}
      return next;
    });
  };

  // --- active conversation state ---
  const [turns, setTurns] = useState<Turn[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [awaiting, setAwaiting] = useState(false);

  // --- pending image upload (cleared once sent) ---
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);

  const menuRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const domain = DOMAINS.find((d) => d.id === domainId)!;

  useEffect(() => {
    try { const s = localStorage.getItem(STORAGE_KEY); if (s) setHistory(JSON.parse(s)); } catch {}
  }, []);

  useEffect(() => {
    const close = (e: MouseEvent) => { if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  useEffect(() => {
    if (!loading) return;
    setStage(0);
    const t = setInterval(() => setStage((s) => (s < STAGES.length - 1 ? s + 1 : s)), 850);
    return () => clearInterval(t);
  }, [loading]);

  // Keep the newest turn in view.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, loading]);

  const persist = (items: any[]) => { setHistory(items); try { localStorage.setItem(STORAGE_KEY, JSON.stringify(items)); } catch {} };

  const greet = () => {
    const h = new Date().getHours();
    return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : h < 21 ? "Good evening" : "Working late";
  };

  // User picked an image from the file dialog.
  const onPickImage = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!f.type.startsWith("image/")) { setError("Please choose an image file."); return; }
    setError(null);
    setImageFile(f);
    setImagePreview(URL.createObjectURL(f));
    // Reset the input so re-picking the same file still fires onChange.
    if (fileRef.current) fileRef.current.value = "";
  };

  const clearImage = () => {
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    setImageFile(null);
    setImagePreview(null);
  };

  // Shared handling of the API response shape (identical for text and image).
  const applyResponse = (data: any) => {
    setThreadId(data.thread_id ?? threadId);
    if (data.awaiting_input) {
      // Triage (or the image "what do you want to know?" prompt) needs more info.
      setAwaiting(true);
      setTurns((prev) => [...prev, { kind: "question", text: data.question }]);
    } else {
      // Final answer — show it, close the thread, and file it in history.
      setAwaiting(false);
      const answer = data.response;
      setTurns((prev) => [...prev, { kind: "answer", data: answer }]);
      const entry = { id: `${Date.now()}`, domainId, result: answer };
      persist([entry, ...history].slice(0, 50));
      setActiveId(entry.id);
      setThreadId(null);
    }
  };

  const handleSubmit = async () => {
    if (loading) return;
    const text = query.trim();

    // Nothing to send unless there's typed text OR an attached image.
    if (!text && !imageFile) return;

    // An attached image ALWAYS starts a fresh query via the image endpoint,
    // even mid-thread — it's a new drug lookup, not a reply to a triage question.
    if (imageFile) {
      const label = text ? text : "📷 Package photo";
      setTurns((prev) => [...prev, { kind: "user", text: label }]);
      setQuery("");
      setLoading(true);
      setError(null);

      const form = new FormData();
      form.append("image", imageFile);
      if (text) form.append("question", text);
      clearImage();

      try {
        const res = await fetch(IMAGE_API_URL, { method: "POST", body: form });
        if (!res.ok) throw new Error(`Backend returned ${res.status}. Is the API running on port 8000?`);
        applyResponse(await res.json());
      } catch (e: any) {
        setError(e.message || "Could not reach the backend.");
      } finally {
        setLoading(false);
      }
      return;
    }

    // Text-only path (unchanged): new query, or a reply to an open triage thread.
    setTurns((prev) => [...prev, { kind: "user", text }]);
    setQuery("");
    setLoading(true);
    setError(null);

    const body = threadId && awaiting
      ? { thread_id: threadId, reply: text }
      : { query: text };

    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`Backend returned ${res.status}. Is the API running on port 8000?`);
      applyResponse(await res.json());
    } catch (e: any) {
      setError(e.message || "Could not reach the backend.");
    } finally {
      setLoading(false);
    }
  };

  const openEntry = (e: any) => {
    // Viewing a past answer opens it as a single-answer conversation.
    setTurns([{ kind: "user", text: e.result.query }, { kind: "answer", data: e.result }]);
    setThreadId(null);
    setAwaiting(false);
    setActiveId(e.id);
    setDomainId(e.domainId || "pharma");
    setError(null);
  };

  const startNew = () => {
    setTurns([]);
    setThreadId(null);
    setAwaiting(false);
    setActiveId(null);
    setError(null);
    setQuery("");
    clearImage();
  };

  if (!user) return <Login onLogin={setUser} />;

  const canSend = (query.trim().length > 0 || !!imageFile) && !loading;
  const empty = turns.length === 0 && !loading;

  return (
    <div style={{ minHeight: "100vh", background: theme.appBg, padding: 16, transition: "background .3s ease" }}>
      <div style={{ display: "flex", height: "calc(100vh - 32px)", background: theme.shell, borderRadius: 16, overflow: "hidden", boxShadow: theme.shellShadow, transition: "background .3s ease" }}>

        {/* SIDEBAR */}
        <aside style={{ width: collapsed ? 0 : 208, background: theme.sidebar, borderRight: collapsed ? "none" : `1px solid ${theme.sidebarBorder}`, padding: collapsed ? "16px 0" : "16px 13px", display: "flex", flexDirection: "column", gap: 15, flexShrink: 0, overflow: "hidden", transition: "width .3s cubic-bezier(.4,0,.2,1), padding .3s ease, background .3s ease" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <Logo size={15} dark={themeKey === "dark"} />
            <span onClick={() => setCollapsed(true)} style={{ cursor: "pointer", color: theme.textFainter, display: "flex", flexShrink: 0 }}><PanelLeftClose size={17} /></span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "6px 5px" }}>
            <span style={{ width: 26, height: 26, borderRadius: 99, background: theme.avatarBg, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, color: theme.avatarText, fontWeight: 600, flexShrink: 0 }}>{user.charAt(0)}</span>
            <div style={{ minWidth: 0 }}>
              <p style={{ fontSize: 12, color: theme.textStrong, margin: 0, fontWeight: 500, whiteSpace: "nowrap" }}>{user}</p>
              <p style={{ fontSize: 10, color: theme.textFaint, margin: 0, whiteSpace: "nowrap" }}>Signed in</p>
            </div>
          </div>

          {/* Theme toggle */}
          <button onClick={toggleTheme} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", background: "transparent", border: `1px solid ${theme.newBtnBorder}`, borderRadius: 10, padding: "8px 11px", fontSize: 12.5, color: theme.textMid, cursor: "pointer", fontFamily: "inherit" }}>
            <span style={{ display: "flex", alignItems: "center", gap: 7 }}>
              {themeKey === "light" ? <Moon size={14} /> : <Sun size={14} />}
              {themeKey === "light" ? "Dark theme" : "Light theme"}
            </span>
          </button>

          <button onClick={startNew} style={{ display: "flex", alignItems: "center", gap: 7, background: "transparent", border: `1px solid ${theme.newBtnBorder}`, borderRadius: 10, padding: "8px 11px", fontSize: 12.5, color: theme.textMid, cursor: "pointer", fontFamily: "inherit" }}>
            <Plus size={14} /> New question
          </button>

          <div style={{ borderTop: `1px solid ${theme.dividerSoft}`, paddingTop: 13, flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0 4px", marginBottom: 8 }}>
              <p style={{ fontSize: 9.5, color: theme.textFainter, letterSpacing: ".08em", textTransform: "uppercase", margin: 0 }}>Recent</p>
              {history.length > 0 && <span onClick={() => persist([])} style={{ fontSize: 10, color: theme.textGhost, cursor: "pointer" }}>Clear</span>}
            </div>
            <div style={{ overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
              {history.length === 0 && <p style={{ fontSize: 12, color: theme.textGhost, padding: "2px 6px", margin: 0 }}>Past questions appear here.</p>}
              {history.map((h) => (
                <div key={h.id} onClick={() => openEntry(h)} style={{ padding: "7px 8px", borderRadius: 8, background: activeId === h.id ? theme.histActive : "transparent", cursor: "pointer" }}>
                  <div style={{ display: "flex", gap: 7, alignItems: "flex-start" }}>
                    <span style={{ width: 5, height: 5, borderRadius: 99, background: DOMAINS.find((d) => d.id === h.domainId)?.dot || "#CCC", marginTop: 5, flexShrink: 0 }} />
                    <span style={{ fontSize: 11.5, color: theme.textMid, lineHeight: 1.4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{h.result.query}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </aside>

        {/* MAIN */}
        <div style={{ flex: 1, position: "relative", display: "flex", flexDirection: "column", minWidth: 0 }}>
          <div style={{ position: "absolute", top: -30, right: -30, width: 360, height: 250, background: `radial-gradient(circle at 70% 30%, ${theme.glow}, transparent 62%)`, pointerEvents: "none" }} />

          {collapsed && (
            <span onClick={() => setCollapsed(false)} style={{ position: "absolute", top: 18, left: 18, cursor: "pointer", color: theme.textFainter, zIndex: 4, display: "flex" }}><PanelLeft size={18} /></span>
          )}

          <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", padding: "26px 32px 0", position: "relative", zIndex: 2 }}>
            <div style={{ maxWidth: 680, margin: "0 auto" }}>

              {empty && (
                <div style={{ minHeight: 280, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center" }}>
                  <p style={{ fontSize: 28, fontWeight: 600, color: theme.textStrong, margin: "0 0 10px", letterSpacing: "-0.025em" }} className="fade-up">{greet()}, {user}</p>
                  <p style={{ fontSize: 14.5, color: theme.textSoft, lineHeight: 1.6, margin: 0, maxWidth: 400 }} className="fade-up-2">Grounded in FDA labels. Scored for confidence. Refused when the evidence is thin.</p>
                </div>
              )}

              {turns.map((turn, i) => {
                if (turn.kind === "user") {
                  return (
                    <div key={i} style={{ display: "flex", justifyContent: "flex-end", margin: "8px 0 22px" }} className="fade-up">
                      <span style={{ background: theme.card, border: `1px solid ${theme.cardBorder}`, borderRadius: 14, padding: "9px 16px", fontSize: 13.5, color: theme.text, boxShadow: "0 1px 3px rgba(0,0,0,.03)", maxWidth: "80%" }}>{turn.text}</span>
                    </div>
                  );
                }
                if (turn.kind === "question") {
                  return (
                    <div key={i} style={{ display: "flex", gap: 12, margin: "8px 0 22px" }} className="fade-up">
                      <LogoMark size={16} animate={false} />
                      <div style={{ flex: 1, minWidth: 0, paddingTop: 2 }}>
                        <p style={{ fontSize: 14.5, lineHeight: 1.75, color: theme.text, margin: 0 }}>{turn.text}</p>
                        <p style={{ fontSize: 11, color: theme.textFaint, margin: "6px 0 0" }}>A little more detail helps me match the right label evidence.</p>
                      </div>
                    </div>
                  );
                }
                return <AnswerTurn key={i} data={turn.data} theme={theme} />;
              })}

              {loading && (
                <div style={{ display: "flex", gap: 12 }}>
                  <LogoMark size={16} animate={true} />
                  <div style={{ paddingTop: 5 }}>
                    <span style={{ fontSize: 13.5, color: theme.textSoft }}>{STAGES[stage]}…</span>
                  </div>
                </div>
              )}

              {error && (
                <div style={{ background: theme.errBg, border: `1px solid ${theme.errBorder}`, borderRadius: 14, padding: "15px 18px" }} className="fade-up">
                  <p style={{ fontSize: 10, color: theme.errLabel, letterSpacing: ".1em", textTransform: "uppercase", margin: "0 0 6px" }}>Request failed</p>
                  <p style={{ fontSize: 13.5, color: theme.errText, margin: 0, lineHeight: 1.55 }}>{error}</p>
                </div>
              )}
            </div>
          </div>

          {/* INPUT */}
          <div style={{ padding: "16px 32px 24px", position: "relative", zIndex: 3 }}>
            <div style={{ maxWidth: 680, margin: "0 auto" }}>
              {/* Pending image preview */}
              {imagePreview && (
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 9 }} className="fade-up">
                  <div style={{ position: "relative", width: 46, height: 46, flexShrink: 0 }}>
                    <img src={imagePreview} alt="upload preview" style={{ width: 46, height: 46, objectFit: "cover", borderRadius: 10, border: `1px solid ${theme.inputBorder}` }} />
                    <button onClick={clearImage} aria-label="Remove image"
                      style={{ position: "absolute", top: -6, right: -6, width: 18, height: 18, borderRadius: 99, border: "none", background: theme.sendBg, color: theme.sendIcon, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <X size={11} />
                    </button>
                  </div>
                  <span style={{ fontSize: 11.5, color: theme.textSoft }}>
                    I'll read the drug name off this package.{query.trim() ? "" : " Add a question, or just send."}
                  </span>
                </div>
              )}

              <input ref={fileRef} type="file" accept="image/*" onChange={onPickImage} style={{ display: "none" }} />

              <div style={{ display: "flex", alignItems: "center", gap: 10, background: theme.inputBar, border: `1px solid ${theme.inputBorder}`, borderRadius: 17, padding: "9px 9px 9px 9px", boxShadow: theme.shellShadow, transition: "background .3s ease, border-color .3s ease" }}>
                {/* Attach image */}
                <button onClick={() => fileRef.current?.click()} aria-label="Attach package photo"
                  style={{ width: 34, height: 34, borderRadius: 11, border: "none", background: imageFile ? theme.attachActiveBg : "transparent", color: imageFile ? theme.attachActiveIcon : theme.attachIcon, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transition: "all .2s ease" }}>
                  <ImagePlus size={17} />
                </button>

                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
                  placeholder={imageFile ? "Add a question about this package (optional)…" : awaiting ? "Type your answer…" : "Ask about a drug's safety, dosage, or interactions"}
                  style={{ flex: 1, border: "none", outline: "none", fontSize: 14, color: theme.text, background: "transparent", minWidth: 0, fontFamily: "inherit" }}
                />

                {/* DOMAIN PICKER — right side */}
                <div style={{ position: "relative" }} ref={menuRef}>
                  <button onClick={() => setMenuOpen((o) => !o)} style={{ display: "flex", alignItems: "center", gap: 6, background: theme.chip, border: `1px solid ${theme.chipBorder}`, borderRadius: 11, padding: "7px 11px", fontSize: 11.5, color: theme.chipText, cursor: "pointer", fontFamily: "inherit", whiteSpace: "nowrap" }}>
                    <span style={{ width: 5, height: 5, borderRadius: 99, background: domain.dot }} />
                    {domain.label}
                    <ChevronDown size={12} color={theme.chevron} />
                  </button>
                  {menuOpen && (
                    <div style={{ position: "absolute", bottom: "calc(100% + 9px)", right: 0, width: 230, background: theme.menu, border: `1px solid ${theme.menuBorder}`, borderRadius: 14, padding: 5, boxShadow: "0 12px 30px rgba(0,0,0,.10)", zIndex: 30 }}>
                      {DOMAINS.map((d) => (
                        <button key={d.id} disabled={!d.available} onClick={() => { setDomainId(d.id); setMenuOpen(false); }}
                          style={{ display: "flex", alignItems: "center", gap: 9, width: "100%", textAlign: "left", background: d.id === domainId ? theme.menuActive : "transparent", border: "none", borderRadius: 10, padding: "9px 10px", cursor: d.available ? "pointer" : "not-allowed", opacity: d.available ? 1 : 0.5, fontFamily: "inherit" }}>
                          <span style={{ width: 6, height: 6, borderRadius: 99, background: d.dot }} />
                          <div>
                            <p style={{ fontSize: 12.5, color: theme.text, margin: 0, fontWeight: d.id === domainId ? 500 : 400 }}>{d.label}</p>
                            <p style={{ fontSize: 10, color: theme.textFaint, margin: "1px 0 0" }}>{d.source}</p>
                          </div>
                          {d.id === domainId && <span style={{ marginLeft: "auto", fontSize: 10, color: theme.textSoft }}>active</span>}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <button onClick={handleSubmit} disabled={!canSend}
                  style={{ width: 34, height: 34, borderRadius: 11, border: "none", background: canSend ? theme.sendBg : theme.sendDisabledBg, color: canSend ? theme.sendIcon : theme.sendDisabledIcon, cursor: canSend ? "pointer" : "default", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transition: "all .2s ease" }}>
                  <ArrowUp size={16} />
                </button>
              </div>
              <p style={{ fontSize: 11, color: theme.textGhost, textAlign: "center", margin: "11px 0 0" }}>Informational only. Not a substitute for professional medical advice.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}