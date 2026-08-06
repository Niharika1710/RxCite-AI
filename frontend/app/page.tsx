"use client";

import { useState, useRef, useEffect } from "react";
import { PanelLeftClose, PanelLeft, ArrowUp, ChevronDown, Plus } from "lucide-react";
import Logo, { LogoMark } from "./logo";
import Login from "./login";

const API_URL = "http://127.0.0.1:8000/api/query";
const STORAGE_KEY = "medintel_history";

const DOMAINS = [
  { id: "pharma",   label: "Pharmaceutical", source: "FDA drug labels",         available: true,  dot: "#5B8DB8" },
  { id: "ayurveda", label: "Ayurveda",       source: "Coming soon",              available: false, dot: "#7BB89A" },
  { id: "home",     label: "Home remedies",  source: "Coming soon",              available: false, dot: "#E0B060" },
];

const STAGES = ["Routing query", "Retrieving evidence", "Validating citations", "Scoring confidence", "Safety gate"];

// A turn in the active conversation.
// kind "user"     -> something the person typed
// kind "question" -> a triage follow-up from the assistant (NO confidence ring)
// kind "answer"   -> a final evidence-grounded answer (ring + citations)
type Turn =
  | { kind: "user"; text: string }
  | { kind: "question"; text: string }
  | { kind: "answer"; data: any };

function ConfidenceRing({ level }: { level: string }) {
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
        <circle cx="20" cy="20" r={r} fill="none" stroke="#ECECEC" strokeWidth="3.5" />
        <circle cx="20" cy="20" r={r} fill="none" stroke={color} strokeWidth="3.5" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={off} style={{ transition: "stroke-dashoffset 1s cubic-bezier(.22,1,.36,1)" }} />
      </svg>
      <span style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 600, color }}>
        {score}
      </span>
    </div>
  );
}

// Renders a single final-answer turn, with its own word-reveal animation.
function AnswerTurn({ data }: { data: any }) {
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
        <p style={{ fontSize: 14.5, lineHeight: 1.75, color: "#1F1F1F", margin: 0 }}>
          {words.map((w, i) => (
            <span key={i} style={{ opacity: i < revealed ? 1 : 0, transition: "opacity .25s ease" }}>{w} </span>
          ))}
        </p>

        {done && (
          <div style={{ marginTop: 18, display: "flex", alignItems: "center", gap: 16 }} className="fade-up">
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <ConfidenceRing level={data.confidence_level} />
              <div>
                <p style={{ fontSize: 12.5, color: "#1F1F1F", margin: 0, fontWeight: 500 }}>{data.confidence_level} confidence</p>
                <p style={{ fontSize: 11, color: "#A5A5A5", margin: "1px 0 0" }}>{data.is_refusal ? "Safety gate blocked" : "Safety gate passed"}</p>
              </div>
            </div>
            {data.citations?.length > 0 && (
              <>
                <span style={{ width: 1, height: 32, background: "#EEE" }} />
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", flex: 1 }}>
                  {data.citations.map((c: any, i: number) => (
                    <a
                      key={i}
                      href={c.url || undefined}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        background: "#fff", border: "1px solid #ECECEC", borderRadius: 8,
                        padding: "5px 9px", fontSize: 10.5, color: "#6E6E6E",
                        textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 5,
                        cursor: c.url ? "pointer" : "default", transition: "all .15s ease",
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.borderColor = "#C9D4E4"; e.currentTarget.style.background = "#F7F9FC"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.borderColor = "#ECECEC"; e.currentTarget.style.background = "#fff"; }}
                    >
                      <b style={{ fontWeight: 500, color: "#1F1F1F", textTransform: "capitalize" }}>{c.drug}</b>
                      <span>· {c.section.replace(/_/g, " ")}</span>
                      <span style={{ color: "#9AABC4", fontSize: 11 }}>↗</span>
                    </a>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {data.recommendation && done && (
          <div style={{ marginTop: 14, background: "#FBF4E6", border: "1px solid #F0E2C0", borderRadius: 12, padding: "12px 15px" }} className="fade-up">
            <p style={{ fontSize: 10, color: "#B08A3A", letterSpacing: ".08em", textTransform: "uppercase", margin: "0 0 5px" }}>What to do instead</p>
            <p style={{ fontSize: 13, color: "#8A5B0B", margin: 0, lineHeight: 1.55 }}>{data.recommendation}</p>
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

  // --- active conversation state ---
  const [turns, setTurns] = useState<Turn[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [awaiting, setAwaiting] = useState(false);

  const menuRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

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

  const handleSubmit = async () => {
    if (!query.trim() || loading) return;
    const text = query.trim();

    // Optimistically show the user's turn.
    setTurns((prev) => [...prev, { kind: "user", text }]);
    setQuery("");
    setLoading(true);
    setError(null);

    // If a thread is open, this message is a reply to a triage question.
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
      const data = await res.json();

      setThreadId(data.thread_id ?? threadId);

      if (data.awaiting_input) {
        // Triage needs more info — show the question, keep the thread open.
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
  };

  if (!user) return <Login onLogin={setUser} />;

  const canSend = query.trim().length > 0 && !loading;
  const empty = turns.length === 0 && !loading;

  return (
    <div style={{ minHeight: "100vh", background: "#D9D9DB", padding: 16 }}>
      <div style={{ display: "flex", height: "calc(100vh - 32px)", background: "#FAFAFA", borderRadius: 16, overflow: "hidden", boxShadow: "0 1px 3px rgba(0,0,0,.04), 0 8px 30px rgba(0,0,0,.06)" }}>

        {/* SIDEBAR */}
        <aside style={{ width: collapsed ? 0 : 208, background: "#FFFFFF", borderRight: collapsed ? "none" : "1px solid #EFEFEF", padding: collapsed ? "16px 0" : "16px 13px", display: "flex", flexDirection: "column", gap: 15, flexShrink: 0, overflow: "hidden", transition: "width .3s cubic-bezier(.4,0,.2,1), padding .3s ease" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <Logo size={15} />
            <span onClick={() => setCollapsed(true)} style={{ cursor: "pointer", color: "#B5B5B5", display: "flex", flexShrink: 0 }}><PanelLeftClose size={17} /></span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "6px 5px" }}>
            <span style={{ width: 26, height: 26, borderRadius: 99, background: "#E8ECF2", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, color: "#6B7686", fontWeight: 600, flexShrink: 0 }}>{user.charAt(0)}</span>
            <div style={{ minWidth: 0 }}>
              <p style={{ fontSize: 12, color: "#2A2A2A", margin: 0, fontWeight: 500, whiteSpace: "nowrap" }}>{user}</p>
              <p style={{ fontSize: 10, color: "#A9A9A9", margin: 0, whiteSpace: "nowrap" }}>Signed in</p>
            </div>
          </div>

          <button onClick={startNew} style={{ display: "flex", alignItems: "center", gap: 7, background: "transparent", border: "1px solid #EAEAEA", borderRadius: 10, padding: "8px 11px", fontSize: 12.5, color: "#4A4A4A", cursor: "pointer", fontFamily: "inherit" }}>
            <Plus size={14} /> New question
          </button>

          <div style={{ borderTop: "1px solid #F0F0F0", paddingTop: 13, flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0 4px", marginBottom: 8 }}>
              <p style={{ fontSize: 9.5, color: "#B5B5B5", letterSpacing: ".08em", textTransform: "uppercase", margin: 0 }}>Recent</p>
              {history.length > 0 && <span onClick={() => persist([])} style={{ fontSize: 10, color: "#BBB", cursor: "pointer" }}>Clear</span>}
            </div>
            <div style={{ overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
              {history.length === 0 && <p style={{ fontSize: 12, color: "#BDBDBD", padding: "2px 6px", margin: 0 }}>Past questions appear here.</p>}
              {history.map((h) => (
                <div key={h.id} onClick={() => openEntry(h)} style={{ padding: "7px 8px", borderRadius: 8, background: activeId === h.id ? "#F3F3F3" : "transparent", cursor: "pointer" }}>
                  <div style={{ display: "flex", gap: 7, alignItems: "flex-start" }}>
                    <span style={{ width: 5, height: 5, borderRadius: 99, background: DOMAINS.find((d) => d.id === h.domainId)?.dot || "#CCC", marginTop: 5, flexShrink: 0 }} />
                    <span style={{ fontSize: 11.5, color: "#4A4A4A", lineHeight: 1.4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{h.result.query}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </aside>

        {/* MAIN */}
        <div style={{ flex: 1, position: "relative", display: "flex", flexDirection: "column", minWidth: 0 }}>
          <div style={{ position: "absolute", top: -30, right: -30, width: 360, height: 250, background: "radial-gradient(circle at 70% 30%, rgba(120,160,235,.16), transparent 62%)", pointerEvents: "none" }} />

          {collapsed && (
            <span onClick={() => setCollapsed(false)} style={{ position: "absolute", top: 18, left: 18, cursor: "pointer", color: "#B5B5B5", zIndex: 4, display: "flex" }}><PanelLeft size={18} /></span>
          )}

          <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", padding: "26px 32px 0", position: "relative", zIndex: 2 }}>
            <div style={{ maxWidth: 680, margin: "0 auto" }}>

              {empty && (
                <div style={{ minHeight: 280, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center" }}>
                  <p style={{ fontSize: 28, fontWeight: 600, color: "#1A1A1A", margin: "0 0 10px", letterSpacing: "-0.025em" }} className="fade-up">{greet()}, {user}</p>
                  <p style={{ fontSize: 14.5, color: "#8E8E8E", lineHeight: 1.6, margin: 0, maxWidth: 400 }} className="fade-up-2">Grounded in FDA labels. Scored for confidence. Refused when the evidence is thin.</p>
                </div>
              )}

              {turns.map((turn, i) => {
                if (turn.kind === "user") {
                  return (
                    <div key={i} style={{ display: "flex", justifyContent: "flex-end", margin: "8px 0 22px" }} className="fade-up">
                      <span style={{ background: "#fff", border: "1px solid #ECECEC", borderRadius: 14, padding: "9px 16px", fontSize: 13.5, color: "#1F1F1F", boxShadow: "0 1px 3px rgba(0,0,0,.03)", maxWidth: "80%" }}>{turn.text}</span>
                    </div>
                  );
                }
                if (turn.kind === "question") {
                  // Triage follow-up: plain assistant message, deliberately NO confidence ring.
                  return (
                    <div key={i} style={{ display: "flex", gap: 12, margin: "8px 0 22px" }} className="fade-up">
                      <LogoMark size={16} animate={false} />
                      <div style={{ flex: 1, minWidth: 0, paddingTop: 2 }}>
                        <p style={{ fontSize: 14.5, lineHeight: 1.75, color: "#1F1F1F", margin: 0 }}>{turn.text}</p>
                        <p style={{ fontSize: 11, color: "#A5A5A5", margin: "6px 0 0" }}>A little more detail helps me match the right label evidence.</p>
                      </div>
                    </div>
                  );
                }
                return <AnswerTurn key={i} data={turn.data} />;
              })}

              {loading && (
                <div style={{ display: "flex", gap: 12 }}>
                  <LogoMark size={16} animate={true} />
                  <div style={{ paddingTop: 5 }}>
                    <span style={{ fontSize: 13.5, color: "#8E8E8E" }}>{STAGES[stage]}…</span>
                  </div>
                </div>
              )}

              {error && (
                <div style={{ background: "#FBEBE7", border: "1px solid #F0D2C7", borderRadius: 14, padding: "15px 18px" }} className="fade-up">
                  <p style={{ fontSize: 10, color: "#B5643E", letterSpacing: ".1em", textTransform: "uppercase", margin: "0 0 6px" }}>Request failed</p>
                  <p style={{ fontSize: 13.5, color: "#9E3B1B", margin: 0, lineHeight: 1.55 }}>{error}</p>
                </div>
              )}
            </div>
          </div>

          {/* INPUT */}
          <div style={{ padding: "16px 32px 24px", position: "relative", zIndex: 3 }}>
            <div style={{ maxWidth: 680, margin: "0 auto" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, background: "#fff", border: "1px solid #E0E0E0", borderRadius: 17, padding: "9px 9px 9px 15px", boxShadow: "0 4px 20px rgba(0,0,0,.08), 0 1px 3px rgba(0,0,0,.04)" }}>
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
                  placeholder={awaiting ? "Type your answer…" : "Ask about a drug's safety, dosage, or interactions"}
                  style={{ flex: 1, border: "none", outline: "none", fontSize: 14, color: "#1F1F1F", background: "transparent", minWidth: 0, fontFamily: "inherit" }}
                />

                {/* DOMAIN PICKER — right side */}
                <div style={{ position: "relative" }} ref={menuRef}>
                  <button onClick={() => setMenuOpen((o) => !o)} style={{ display: "flex", alignItems: "center", gap: 6, background: "#F5F6F8", border: "1px solid #ECEDF0", borderRadius: 11, padding: "7px 11px", fontSize: 11.5, color: "#4A515C", cursor: "pointer", fontFamily: "inherit", whiteSpace: "nowrap" }}>
                    <span style={{ width: 5, height: 5, borderRadius: 99, background: domain.dot }} />
                    {domain.label}
                    <ChevronDown size={12} color="#B6BCC6" />
                  </button>
                  {menuOpen && (
                    <div style={{ position: "absolute", bottom: "calc(100% + 9px)", right: 0, width: 230, background: "#fff", border: "1px solid #EAEAEA", borderRadius: 14, padding: 5, boxShadow: "0 12px 30px rgba(0,0,0,.10)", zIndex: 30 }}>
                      {DOMAINS.map((d) => (
                        <button key={d.id} disabled={!d.available} onClick={() => { setDomainId(d.id); setMenuOpen(false); }}
                          style={{ display: "flex", alignItems: "center", gap: 9, width: "100%", textAlign: "left", background: d.id === domainId ? "#F5F6F8" : "transparent", border: "none", borderRadius: 10, padding: "9px 10px", cursor: d.available ? "pointer" : "not-allowed", opacity: d.available ? 1 : 0.5, fontFamily: "inherit" }}>
                          <span style={{ width: 6, height: 6, borderRadius: 99, background: d.dot }} />
                          <div>
                            <p style={{ fontSize: 12.5, color: "#1F1F1F", margin: 0, fontWeight: d.id === domainId ? 500 : 400 }}>{d.label}</p>
                            <p style={{ fontSize: 10, color: "#A5A5A5", margin: "1px 0 0" }}>{d.source}</p>
                          </div>
                          {d.id === domainId && <span style={{ marginLeft: "auto", fontSize: 10, color: "#9A9A9A" }}>active</span>}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <button onClick={handleSubmit} disabled={!canSend}
                  style={{ width: 34, height: 34, borderRadius: 11, border: "none", background: canSend ? "#151515" : "#EDEDED", color: canSend ? "#fff" : "#B5B5B5", cursor: canSend ? "pointer" : "default", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transition: "all .2s ease" }}>
                  <ArrowUp size={16} />
                </button>
              </div>
              <p style={{ fontSize: 11, color: "#BDBDBD", textAlign: "center", margin: "11px 0 0" }}>Informational only. Not a substitute for professional medical advice.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}