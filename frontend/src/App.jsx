import { useState, useEffect, useRef, useCallback } from "react";
// import "./index.css";
import "./app.css"

const API_URL = "http://127.0.0.1:8000";

// ============================================================
// UTILITIES
// ============================================================

function formatTime(isoStr) {
  if (!isoStr) return "—";
  const d = new Date(isoStr);
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function readStoredJSON(key, fallback) {
  try {
    const value = localStorage.getItem(key);
    return value ? JSON.parse(value) : fallback;
  } catch {
    return fallback;
  }
}

function readHistory() {
  return readStoredJSON("foodintel-history", []).map((entry, index) => ({
    ...entry,
    id: entry.id || `legacy-${entry.timestamp || "unknown"}-${index}`,
    status: entry.status || "completed",
    duration: entry.duration ?? entry.result?.scan_duration_ms,
    result: entry.result || null,
  }));
}
function normalizeResult(data) {
  if (!data || typeof data !== "object") return data;
  if (data.automatic_facts && typeof data.automatic_facts === "object") {
    return {
      ...data,
      website: data.website || data.automatic_facts.final_url,
      audit_timestamp: data.audit_timestamp || new Date().toISOString(),
      ai_analysis: data.ai_analysis || data.automatic_facts.ai_analysis || null,
    };
  }
  const { ai_analysis, ...facts } = data;
  return {
    website: data.website,
    audit_timestamp: data.audit_timestamp || new Date().toISOString(),
    scan_duration_ms: data.scan_duration_ms ?? data.response_time_ms,
    automatic_facts: facts,
    ai_analysis: ai_analysis || null,
  };
}
function copyToClipboard(text, onSuccess) {
  if (!text) return;
  navigator.clipboard
    .writeText(text)
    .then(() => onSuccess && onSuccess())
    .catch(() => { });
}

// ============================================================
// TOAST SYSTEM
// ============================================================

function ToastContainer({ toasts }) {
  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <div key={t.id} className={`toast toast-${t.type || "info"}`}>
          <span className="toast-icon">
            {t.type === "success" ? "✓" : t.type === "error" ? "✕" : "ℹ"}
          </span>
          {t.message}
        </div>
      ))}
    </div>
  );
}

function useToast() {
  const [toasts, setToasts] = useState([]);
  const show = useCallback((message, type = "info") => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 3000);
  }, []);
  return { toasts, show };
}

// ============================================================
// COPY BUTTON
// ============================================================

function CopyBtn({ text, toast }) {
  const [copied, setCopied] = useState(false);
  if (!text) return null;
  return (
    <button
      className="copy-btn"
      title="Copy"
      onClick={() => {
        copyToClipboard(text, () => {
          setCopied(true);
          toast?.("Copied!", "success");
          setTimeout(() => setCopied(false), 2000);
        });
      }}
    >
      {copied ? "✓" : "⎘"}
    </button>
  );
}

// ============================================================
// AUTH PAGES
// ============================================================

function AuthPage({ onSkip, initialMode = "login" }) {
  const [mode, setMode] = useState(initialMode);
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [notice, setNotice] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    setNotice("Authentication is not connected yet. Your information was not submitted.");
  };

  return (
    <div className="auth-page">
      <div className="auth-bg" />
      <div className="auth-card">
        <div className="auth-logo">
          <img src="/logo.jpg" alt="FoodIntel" />
        </div>
        <h1 className="auth-title">FoodIntel</h1>
        <p className="auth-subtitle">AI Restaurant Website Intelligence</p>

        <div className="auth-tabs">
          {["login", "signup"].map((m) => (
            <button
              key={m}
              className={mode === m ? "auth-tab active" : "auth-tab"}
              onClick={() => setMode(m)}
            >
              {m === "login" ? "Sign In" : "Sign Up"}
            </button>
          ))}
        </div>

        {mode === "forgot" ? (
          <form className="auth-form" onSubmit={handleSubmit}>
            <h3>Reset Password</h3>
            <p className="auth-note">
              Enter your email to receive a reset link.
            </p>
            <div className="auth-field">
              <label>Email</label>
              <input
                type="email"
                placeholder="you@example.com"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </div>
            <button className="auth-submit" type="submit">
              Send Reset Link
            </button>
            <button
              className="auth-link"
              type="button"
              onClick={() => setMode("login")}
            >
              ← Back to Sign In
            </button>
          </form>
        ) : (
          <form className="auth-form" onSubmit={handleSubmit}>
            {mode === "signup" && (
              <div className="auth-field">
                <label>Full Name</label>
                <input
                  type="text"
                  placeholder="Your name"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </div>
            )}
            <div className="auth-field">
              <label>Email</label>
              <input
                type="email"
                placeholder="you@example.com"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </div>
            <div className="auth-field">
              <label>Password</label>
              <input
                type="password"
                placeholder="••••••••"
                value={form.password}
                onChange={(e) =>
                  setForm({ ...form, password: e.target.value })
                }
              />
            </div>
            {mode === "login" && (
              <button
                className="auth-link"
                type="button"
                onClick={() => setMode("forgot")}
              >
                Forgot password?
              </button>
            )}
            <button className="auth-submit" type="submit">
              {mode === "login" ? "Sign In" : "Create Account"}
            </button>
          </form>
        )}

        <div className="auth-divider">or</div>
        {notice && <p className="auth-note" role="status">{notice}</p>}
        <button className="auth-guest" onClick={onSkip}>
          Continue as Guest →
        </button>
      </div>
    </div>
  );
}

// ============================================================
// MAIN APP
// ============================================================

const SECTIONS = [
  { id: "overview", icon: "⌂", label: "Dashboard / Overview" },
  { id: "new-scan", icon: "+", label: "New Audit / Scan Website" },
  { id: "profile", icon: "◉", label: "Restaurant Profile" },
  { id: "menu", icon: "🍽", label: "Menu" },
  { id: "contact", icon: "☎", label: "Contact & Location" },
  { id: "location", icon: "⌖", label: "Location Details" },
  { id: "hours", icon: "🕐", label: "Opening Hours" },
  { id: "reservation", icon: "📅", label: "Reservations" },
  { id: "ordering", icon: "🛒", label: "Online Ordering" },
  { id: "social", icon: "◎", label: "Social Media" },
  { id: "about", icon: "ⓘ", label: "About" },
  { id: "website", icon: "◈", label: "SEO & Website" },
  { id: "technical", icon: "⚙", label: "Technical Details" },
  { id: "ai", icon: "✦", label: "AI Insights" },
  { id: "history", icon: "◷", label: "Scan History" },
  { id: "scan", icon: "▤", label: "Technical Scan Details" },
  { id: "report", icon: "↓", label: "Reports" },
  { id: "settings", icon: "⚙", label: "Settings" },
];

export default function App() {
  const [showAuth, setShowAuth] = useState(false);
  const [authMode, setAuthMode] = useState("login");
  const [darkMode, setDarkMode] = useState(() => {
    return localStorage.getItem("foodintel-dark") === "true";
  });
  const [result, setResult] = useState(() => readStoredJSON("foodintel-result", null));
  const [url, setUrl] = useState(() => readStoredJSON("foodintel-result", null)?.website || "");
  const [activeSection, setActiveSection] = useState(() => localStorage.getItem("foodintel-section") || "overview");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [scanHistory, setScanHistory] = useState(readHistory);
  const [preferences, setPreferences] = useState(() => readStoredJSON("foodintel-preferences", { notifications: true }));
  const [scanProgress, setScanProgress] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { toasts, show: showToast } = useToast();
  const inputRef = useRef(null);

  useEffect(() => {
    document.documentElement.setAttribute(
      "data-theme",
      darkMode ? "dark" : "light"
    );
    localStorage.setItem("foodintel-dark", darkMode);
  }, [darkMode]);

  useEffect(() => {
    localStorage.setItem("foodintel-section", activeSection);
  }, [activeSection]);

  useEffect(() => {
    localStorage.setItem("foodintel-preferences", JSON.stringify(preferences));
  }, [preferences]);

  useEffect(() => {
    localStorage.setItem("foodintel-history", JSON.stringify(scanHistory));
  }, [scanHistory]);

  const runAudit = async (targetUrl) => {
    const scanUrl = (targetUrl || url).trim();
    if (!scanUrl) {
      setError("Please enter a restaurant website URL.");
      return;
    }

    setLoading(true);
    setError("");
    setScanProgress("Connecting to website...");
    const scanStartedAt = Date.now();

    // Simulate progress messages
    const progressSteps = [
      "Connecting to website...",
      "Fetching page content...",
      "Rendering with browser engine...",
      "Extracting menu information...",
      "Detecting contact & location...",
      "Analyzing social media...",
      "Running AI intelligence...",
      "Compiling report...",
    ];
    let step = 0;
    const progressInterval = setInterval(() => {
      step = Math.min(step + 1, progressSteps.length - 1);
      setScanProgress(progressSteps[step]);
    }, 3500);

    try {
      let response;
      try {
        response = await fetch(`${API_URL}/audit`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: scanUrl }),
        });
      } catch {
        throw new Error("Cannot reach the backend. Start it with: uvicorn main:app --reload --port 8000");
      }

      const raw = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof raw.detail === "string" ? raw.detail : raw.message || "Website scan failed."
        );
      }
      if (raw.scan_successful === false) {
        throw new Error(raw.error || "Website scan failed.");
      }

      const data = normalizeResult(raw);

      setResult(data);
      localStorage.setItem("foodintel-result", JSON.stringify(data));
      setActiveSection("overview");
      setSidebarOpen(false);
      if (preferences.notifications) showToast("Scan completed successfully!", "success");

      // Save to history
      const entry = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        url: scanUrl,
        name:
          data.automatic_facts?.restaurant?.name || scanUrl,
        timestamp: data.audit_timestamp,
        duration: data.scan_duration_ms,
        status: "completed",
        score: data.ai_analysis?.score,
        result: data,
      };
      setScanHistory((prev) => {
        const updated = [entry, ...prev].slice(0, 20);
        localStorage.setItem("foodintel-history", JSON.stringify(updated));
        return updated;
      });
    } catch (err) {
      setError(err.message || "Unable to scan the website.");
      if (preferences.notifications) showToast(err.message || "Scan failed.", "error");
      const failedEntry = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        url: scanUrl,
        name: scanUrl,
        timestamp: new Date().toISOString(),
        duration: Date.now() - scanStartedAt,
        status: "failed",
        error: err.message || "Unable to scan the website.",
      };
      setScanHistory((prev) => {
        const updated = [failedEntry, ...prev].slice(0, 20);
        localStorage.setItem("foodintel-history", JSON.stringify(updated));
        return updated;
      });
    } finally {
      clearInterval(progressInterval);
      setLoading(false);
      setScanProgress("");
    }
  };

  const facts = result?.automatic_facts || {};
  const restaurant = facts.restaurant || {};
  const aiAnalysis = result?.ai_analysis || {};

  if (showAuth) {
    return <AuthPage initialMode={authMode} onSkip={() => setShowAuth(false)} />;
  }

  return (
    <div className={`app ${darkMode ? "dark" : ""}`}>
      <ToastContainer toasts={toasts} />

      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
        <div className="brand">
          <img src="/logo.jpg" alt="FoodIntel" className="brand-logo" />
          <div>
            <h1>FOODINTEL</h1>
            <span>Restaurant Intelligence</span>
          </div>
        </div>

        <div className="sidebar-label">INTELLIGENCE</div>

        <nav className="side-nav">
          {SECTIONS.map((section) => (
            <button
              key={section.id}
              className={activeSection === section.id ? "nav-item active" : "nav-item"}
              onClick={() => {
                if (section.id === "new-scan") {
                  setResult(null);
                  localStorage.removeItem("foodintel-result");
                  setUrl("");
                  setError("");
                }
                setActiveSection(section.id);
                setSidebarOpen(false);
              }}
            >
              <span className="nav-icon">{section.icon}</span>
              <span>{section.label}</span>
            </button>
          ))}
        </nav>

        {scanHistory.length > 0 && (
          <div className="recent-scans">
            <div className="sidebar-label" style={{ marginTop: "16px" }}>RECENT SCANS</div>
            {scanHistory.slice(0, 4).map((h) => (
              <button
                key={h.id || `${h.url}-${h.timestamp}`}
                className="history-item"
                onClick={() => {
                  if (h.result) {
                    setResult(h.result);
                    setUrl(h.url);
                    localStorage.setItem("foodintel-result", JSON.stringify(h.result));
                    setActiveSection("overview");
                  } else if (h.status === "completed") {
                    setUrl(h.url);
                    runAudit(h.url);
                  } else {
                    setActiveSection("history");
                  }
                }}
                title={h.url}
              >
                <span className="history-dot" />
                <span className="history-name">{h.name}</span>
              </button>
            ))}
          </div>
        )}

        <div className="sidebar-bottom">
          <button className="theme-button" onClick={() => setDarkMode(!darkMode)}>
            <span>{darkMode ? "☀" : "☾"}</span>
            {darkMode ? "Light Mode" : "Dark Mode"}
          </button>

        </div>
      </aside>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Main */}
      <main className="main-content">
        {/* Topbar */}
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="mobile-menu-btn"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              aria-label="Menu"
            >
              ☰
            </button>
            <div>
              <span className="eyebrow">FOOD WEBSITE INTELLIGENCE</span>
              <h2>Restaurant Website Auditor</h2>
            </div>
          </div>

          <div className="topbar-right">
            <button className="topbar-btn auth-topbar-btn" onClick={() => { setAuthMode("login"); setShowAuth(true); }}>Sign In</button>
            <button className="topbar-btn auth-topbar-btn signup-topbar-btn" onClick={() => { setAuthMode("signup"); setShowAuth(true); }}>Sign Up</button>
            {result && (
              <>
                <button
                  className="topbar-btn secondary"
                  onClick={() => {
                    setResult(null);
                    localStorage.removeItem("foodintel-result");
                    setUrl("");
                    setError("");
                    setActiveSection("overview");
                  }}
                >
                  ✕ New Audit
                </button>
                <button
                  className="topbar-btn"
                  onClick={() => runAudit(url)}
                  disabled={loading}
                >
                  ↺ Re-scan
                </button>
                <a
                  href={result.website}
                  target="_blank"
                  rel="noreferrer"
                  className="topbar-btn accent"
                >
                  Open Site ↗
                </a>
              </>
            )}
          </div>
        </header>

        {/* Scanner */}
        <section className="scanner-section">
          <div className="scanner-card">
            {/* Restaurant profile when result available */}
            {result && (
              <div className="restaurant-profile">
                <div className="restaurant-avatar-wrap">
                  {restaurant.favicon_url ? (
                    <img
                      src={restaurant.favicon_url}
                      alt={restaurant.name}
                      className="restaurant-favicon"
                      onError={(e) => {
                        e.target.style.display = "none";
                        e.target.nextSibling.style.display = "flex";
                      }}
                    />
                  ) : null}
                  <div
                    className="restaurant-initial"
                    style={restaurant.favicon_url ? { display: "none" } : {}}
                  >
                    {(restaurant.name || "R").charAt(0).toUpperCase()}
                  </div>
                </div>
                <div className="restaurant-info">
                  <h3>{restaurant.name || "Restaurant Website"}</h3>
                  <a
                    href={result.website}
                    target="_blank"
                    rel="noreferrer"
                    className="restaurant-url"
                  >
                    {result.website}
                  </a>
                </div>
                <div className="restaurant-badges">
                  <span className="badge badge-status">
                    {facts.status_code || 200} OK
                  </span>
                  <span className="badge">
                    {facts.scanner_method || "HTTP"}
                  </span>
                  <span className="badge">
                    {result.scan_duration_ms
                      ? `${(result.scan_duration_ms / 1000).toFixed(1)}s`
                      : "—"}
                  </span>
                </div>
              </div>
            )}

            {/* URL Input */}
            <div className="scanner-input-row">
              <div className="scanner-icon-wrap">
                <span>⌕</span>
              </div>
              <input
                ref={inputRef}
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && runAudit()}
                placeholder="https://restaurant-website.com"
                disabled={loading}
                id="url-input"
                className="url-input"
              />
              <button
                className="scan-btn"
                onClick={() => runAudit()}
                disabled={loading}
                id="scan-button"
              >
                {loading ? (
                  <>
                    <span className="spinner" />
                    Scanning...
                  </>
                ) : (
                  "Scan Website →"
                )}
              </button>
            </div>

            {/* Progress */}
            {loading && (
              <div className="scan-progress">
                <div className="scan-progress-bar">
                  <div className="scan-progress-fill" />
                </div>
                <span className="scan-progress-label">{scanProgress}</span>
              </div>
            )}

            {error && (
              <div className="error-message" role="alert">
                <span>⚠</span> {error}
              </div>
            )}

            {/* Scan Meta */}
            {result && (
              <div className="scan-meta-row">
                <div className="scan-meta-item">
                  <span>SCANNED</span>
                  <strong>{formatTime(result.audit_timestamp)}</strong>
                </div>
                <div className="scan-meta-item">
                  <span>DURATION</span>
                  <strong>
                    {result.scan_duration_ms
                      ? `${(result.scan_duration_ms / 1000).toFixed(1)}s`
                      : "—"}
                  </strong>
                </div>
                <div className="scan-meta-item">
                  <span>METHOD</span>
                  <strong>{facts.scanner_method || "HTTP"}</strong>
                </div>
                <div className="scan-meta-item">
                  <span>STATUS</span>
                  <strong className="text-success">
                    {facts.status_code || 200} · Live
                  </strong>
                </div>
                <div className="scan-meta-item">
                  <span>WORDS</span>
                  <strong>{facts.content?.word_count?.toLocaleString() || 0}</strong>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Content Area */}
        <section className="content-area">
          {!result ? (
            activeSection === "history" ? (
              <HistorySection history={scanHistory} onOpen={(entry) => {
                if (entry.result) {
                  setResult(entry.result);
                  setUrl(entry.url);
                  localStorage.setItem("foodintel-result", JSON.stringify(entry.result));
                  setActiveSection("overview");
                }
              }} onRescan={(entry) => { setUrl(entry.url); runAudit(entry.url); }} onDelete={(id) => setScanHistory((prev) => {
                const updated = prev.filter((entry) => entry.id !== id);
                localStorage.setItem("foodintel-history", JSON.stringify(updated));
                return updated;
              })} onClear={() => { setScanHistory([]); localStorage.setItem("foodintel-history", "[]"); showToast("Scan history cleared.", "success"); }} toast={showToast} />
            ) : activeSection === "settings" ? (
              <SettingsSection darkMode={darkMode} setDarkMode={setDarkMode} preferences={preferences} setPreferences={setPreferences} />
            ) : activeSection === "new-scan" ? (
              <WelcomePanel />
            ) : activeSection === "report" ? (
              <EmptyState icon="↓" message="Select a scan to view its report." detail="Run a new audit or open a previous result from Scan History." />
            ) : activeSection === "overview" ? (
              <WelcomePanel recentScans={scanHistory.slice(0, 5)} onOpenScan={(entry) => {
                if (entry.result) {
                  setResult(entry.result);
                  setUrl(entry.url);
                  localStorage.setItem("foodintel-result", JSON.stringify(entry.result));
                }
              }} onShowHistory={() => setActiveSection("history")} />
            ) : (
              <EmptyState icon="⌁" message="Scan a website to view this intelligence." detail="Your scan results will populate this section." />
            )
          ) : (
            <SectionRenderer
              activeSection={activeSection}
              facts={facts}
              result={result}
              aiAnalysis={aiAnalysis}
              toast={showToast}
              onSectionChange={setActiveSection}
              history={scanHistory}
              onHistoryOpen={(entry) => {
                if (entry.result) {
                  setResult(entry.result);
                  setUrl(entry.url);
                  localStorage.setItem("foodintel-result", JSON.stringify(entry.result));
                  setActiveSection("overview");
                }
              }}
              onHistoryRescan={(entry) => { setUrl(entry.url); runAudit(entry.url); }}
              onHistoryDelete={(id) => setScanHistory((prev) => {
                const updated = prev.filter((entry) => entry.id !== id);
                localStorage.setItem("foodintel-history", JSON.stringify(updated));
                return updated;
              })}
              onHistoryClear={() => { setScanHistory([]); localStorage.setItem("foodintel-history", "[]"); showToast("Scan history cleared.", "success"); }}
              darkMode={darkMode}
              setDarkMode={setDarkMode}
              preferences={preferences}
              setPreferences={setPreferences}
            />
          )}
        </section>
      </main>
    </div>
  );
}

// ============================================================
// WELCOME PANEL
// ============================================================

function WelcomePanel({ recentScans = [], onOpenScan, onShowHistory }) {
  return (
    <div className="welcome-panel">
      <div className="welcome-logo">
        <img src="/logo.jpg" alt="FoodIntel" />
      </div>
      <h2>AI Food Website Intelligence</h2>
      <p>
        Paste any public restaurant, café, bakery, or food business URL above to
        extract menus, contact details, location, hours, reservations, social
        profiles and AI-powered insights in seconds.
      </p>

      <div className="welcome-steps">
        {[
          { num: "01", title: "Scan", desc: "Enter any food website URL" },
          { num: "02", title: "Extract", desc: "AI extracts real business data" },
          { num: "03", title: "Explore", desc: "Browse organized intelligence" },
          { num: "04", title: "Report", desc: "Download structured report" },
        ].map((step) => (
          <div key={step.num} className="welcome-step">
            <span className="step-num">{step.num}</span>
            <strong>{step.title}</strong>
            <small>{step.desc}</small>
          </div>
        ))}
      </div>

      <div className="welcome-features">
        {[
          "🍽 Menu extraction",
          "☎ Contact detection",
          "⌖ Location & maps",
          "🕐 Opening hours",
          "📅 Reservations",
          "🛒 Online ordering",
          "◎ Social media",
          "✦ AI insights",
          "↓ PDF/JSON report",
        ].map((f) => (
          <span key={f} className="welcome-feature-pill">{f}</span>
        ))}
      </div>

      {recentScans.length > 0 && (
        <div className="dashboard-recent">
          <div className="dashboard-recent-heading">
            <div>
              <span className="mini-label">WORKSPACE</span>
              <h3>Recent scans</h3>
            </div>
            <button className="text-action" onClick={onShowHistory}>View history</button>
          </div>
          {recentScans.map((entry) => (
            <button key={entry.id || `${entry.url}-${entry.timestamp}`} className="dashboard-recent-row" onClick={() => onOpenScan?.(entry)}>
              <span className={`status-indicator ${entry.status === "failed" ? "status-failed" : ""}`} />
              <span className="dashboard-recent-name">{entry.name}</span>
              <span className="dashboard-recent-date">{formatTime(entry.timestamp)}</span>
              <span className="dashboard-recent-score">{entry.score == null ? "—" : `${entry.score}/100`}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function HistorySection({ history, onOpen, onRescan, onDelete, onClear, toast }) {
  const [query, setQuery] = useState("");
  const filteredHistory = history.filter((entry) =>
    `${entry.name} ${entry.url} ${entry.status}`.toLowerCase().includes(query.toLowerCase())
  );

  const exportEntry = (entry) => {
    if (!entry.result) return;
    const blob = new Blob([JSON.stringify(entry.result, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    const host = (() => {
      try { return new URL(entry.url).hostname; } catch { return "scan"; }
    })();
    link.download = `foodintel-${host}-report.json`;
    link.click();
    URL.revokeObjectURL(link.href);
    toast("Report downloaded.", "success");
  };

  return (
    <div className="section">
      <div className="section-heading history-heading">
        <div>
          <span className="eyebrow">WORKSPACE</span>
          <h2>Scan History</h2>
          <p>{history.length} saved {history.length === 1 ? "scan" : "scans"} on this device.</p>
        </div>
        {history.length > 0 && <button className="danger-action" onClick={onClear}>Clear history</button>}
      </div>

      <div className="history-toolbar">
        <label className="history-search">
          <span aria-hidden="true">⌕</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search restaurant or website" aria-label="Search scan history" />
        </label>
        <span className="history-count">{filteredHistory.length} results</span>
      </div>

      {filteredHistory.length ? (
        <div className="history-table-wrap">
          <table className="history-table">
            <thead><tr><th>Restaurant</th><th>Website</th><th>Scanned</th><th>Duration</th><th>Status</th><th>Score</th><th>Actions</th></tr></thead>
            <tbody>
              {filteredHistory.map((entry) => (
                <tr key={entry.id || `${entry.url}-${entry.timestamp}`}>
                  <td className="history-restaurant">{entry.name || entry.url}</td>
                  <td><a href={entry.url} target="_blank" rel="noreferrer" className="table-link">{entry.url}</a></td>
                  <td>{formatTime(entry.timestamp)}</td>
                  <td>{entry.duration ? `${(entry.duration / 1000).toFixed(1)}s` : "—"}</td>
                  <td><span className={`history-status ${entry.status === "failed" ? "failed" : "completed"}`}>{entry.status || "completed"}</span></td>
                  <td>{entry.score == null ? "—" : `${entry.score}/100`}</td>
                  <td>
                    <div className="history-actions">
                      <button title="Open saved result" aria-label="Open saved result" disabled={!entry.result} onClick={() => onOpen?.(entry)}>View</button>
                      <button title="Scan this website again" aria-label="Re-scan website" onClick={() => onRescan?.(entry)}>Re-scan</button>
                      <button title="Download JSON report" aria-label="Download report" disabled={!entry.result} onClick={() => exportEntry(entry)}>Export</button>
                      <button className="history-delete" title="Delete history item" aria-label="Delete history item" onClick={() => onDelete?.(entry.id)}>Delete</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState icon="◷" message={history.length ? "No scans match this search." : "No scans saved yet."} detail={history.length ? "Try a different restaurant name or website address." : "Completed and failed scan attempts will appear here."} />
      )}
    </div>
  );
}

function SettingsSection({ darkMode, setDarkMode, preferences, setPreferences }) {
  return (
    <div className="section">
      <SectionHeading eyebrow="PREFERENCES" title="Settings" description="Your interface preferences are saved locally on this device." />
      <div className="settings-list">
        <div className="settings-row">
          <div><strong>Appearance</strong><span>Choose a light or dark workspace.</span></div>
          <div className="segmented-control" role="group" aria-label="Appearance">
            <button className={!darkMode ? "selected" : ""} onClick={() => setDarkMode(false)}>Light</button>
            <button className={darkMode ? "selected" : ""} onClick={() => setDarkMode(true)}>Dark</button>
          </div>
        </div>
        <label className="settings-row">
          <div><strong>Scan notifications</strong><span>Show completion and error notifications.</span></div>
          <input type="checkbox" checked={preferences.notifications !== false} onChange={(event) => setPreferences((previous) => ({ ...previous, notifications: event.target.checked }))} />
        </label>
        <div className="settings-row">
          <div><strong>Data storage</strong><span>Audit results and history stay in this browser’s local storage.</span></div>
          <span className="storage-status">On this device</span>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// SECTION RENDERER
// ============================================================

function SectionRenderer({ activeSection, facts, result, aiAnalysis, toast, onSectionChange, history, onHistoryOpen, onHistoryRescan, onHistoryDelete, onHistoryClear, darkMode, setDarkMode, preferences, setPreferences }) {
  const restaurant = facts.restaurant || {};
  const menu = facts.menu || {};
  const contact = facts.contact || {};
  const social = facts.social_media || {};
  const features = facts.features || {};
  const content = facts.content || {};
  const seo = facts.seo || {};
  const technical = facts.technical || {};
  const location = facts.location || {};
  const openingHours = facts.opening_hours || {};
  const reservations = facts.reservations || {};
  const ordering = facts.ordering || {};
  const about = facts.about || {};

  switch (activeSection) {
    case "overview":
      return (
        <OverviewSection
          facts={facts}
          restaurant={restaurant}
          result={result}
          aiAnalysis={aiAnalysis}
          features={features}
          onNav={onSectionChange}
          toast={toast}
        />
      );
    case "new-scan":
      return <EmptyState icon="+" message="Ready for a new website audit." detail="Enter a restaurant website in the scanner above to begin." />;
    case "profile":
      return <AboutSection restaurant={restaurant} about={about} content={content} />;
    case "menu":
      return <MenuSection menu={menu} toast={toast} />;
    case "contact":
      return <ContactSection contact={contact} navigation={facts.navigation} toast={toast} />;
    case "location":
      return <LocationSection location={location} contact={contact} toast={toast} />;
    case "hours":
      return <HoursSection openingHours={openingHours} />;
    case "reservation":
      return <ReservationSection reservations={reservations} />;
    case "ordering":
      return <OrderingSection ordering={ordering} />;
    case "social":
      return <SocialSection social={social} toast={toast} />;
    case "about":
      return <AboutSection restaurant={restaurant} about={about} content={content} />;
    case "website":
      return <WebsiteSection facts={facts} seo={seo} content={content} />;
    case "technical":
      return <TechnicalSection technical={technical} facts={facts} />;
    case "ai":
      return <AISection analysis={aiAnalysis} />;
    case "scan":
      return <ScanDetailsSection facts={facts} result={result} />;
    case "report":
      return <ReportSection result={result} toast={toast} />;
    case "history":
      return <HistorySection history={history || []} onOpen={onHistoryOpen} onRescan={onHistoryRescan} onDelete={onHistoryDelete} onClear={onHistoryClear} toast={toast} />;
    case "settings":
      return <SettingsSection darkMode={darkMode} setDarkMode={setDarkMode} preferences={preferences} setPreferences={setPreferences} />;
    default:
      return null;
  }
}

// ============================================================
// SECTION: OVERVIEW
// ============================================================

function OverviewSection({ facts, restaurant, result, aiAnalysis, features, onNav, toast }) {
  const featureList = [
    { key: "menu", label: "Menu", nav: "menu", icon: "🍽" },
    { key: "reservation", label: "Reservations", nav: "reservation", icon: "📅" },
    { key: "online_ordering", label: "Online Ordering", nav: "ordering", icon: "🛒" },
    { key: "contact", label: "Contact Info", nav: "contact", icon: "☎" },
    { key: "social_media", label: "Social Media", nav: "social", icon: "◎" },
    { key: "email", label: "Email", nav: "contact", icon: "@" },
    { key: "phone", label: "Phone", nav: "contact", icon: "📞" },
    { key: "address", label: "Address", nav: "location", icon: "⌖" },
  ];

  const detected = featureList.filter(f => features[f.key]);
  const missing = featureList.filter(f => !features[f.key]);

  return (
    <div className="section">
      <SectionHeading
        eyebrow="RESTAURANT OVERVIEW"
        title={restaurant.name || "Restaurant Website"}
        description="Structured overview of information discovered from the scanned website."
      />

      {/* Hero profile */}
      <div className="overview-hero">
        <div className="overview-brand">
          <div className="overview-avatar">
            {restaurant.favicon_url ? (
              <img
                src={restaurant.favicon_url}
                alt={restaurant.name}
                onError={(e) => {
                  e.target.style.display = "none";
                  e.target.nextSibling.style.display = "flex";
                }}
              />
            ) : null}
            <div
              className="overview-initial"
              style={restaurant.favicon_url ? { display: "none" } : {}}
            >
              {(restaurant.name || "R").charAt(0).toUpperCase()}
            </div>
          </div>
          <div className="overview-brand-info">
            <h3>{restaurant.name || "Restaurant Website"}</h3>
            <a
              href={result.website}
              target="_blank"
              rel="noreferrer"
              className="overview-url"
            >
              {facts.final_url || result.website}
            </a>
            {restaurant.language && (
              <span className="badge" style={{ marginTop: 6 }}>
                {restaurant.language.toUpperCase()}
              </span>
            )}
          </div>
        </div>

        {restaurant.description && (
          <p className="overview-description">{restaurant.description}</p>
        )}
      </div>

      {/* Quick stats */}
      <div className="stats-row">
        <StatCard label="Status" value={`${facts.status_code || 200} OK`} green />
        <StatCard label="Words" value={(facts.content?.word_count || 0).toLocaleString()} />
        <StatCard label="Images" value={facts.media?.total_images || 0} />
        <StatCard label="Int. Links" value={facts.scanner?.internal_link_count || 0} />
        <StatCard
          label="HTTPS"
          value={facts.technical?.https ? "Yes" : "No"}
          green={facts.technical?.https}
        />
        <StatCard
          label="Mobile"
          value={facts.technical?.mobile_responsive ? "Yes" : "No"}
          green={facts.technical?.mobile_responsive}
        />
      </div>

      {/* Feature grid */}
      <div className="feature-section">
        <div className="feature-section-heading">
          <span className="mini-label">DETECTED FEATURES</span>
          <span className="feature-count">
            {detected.length}/{featureList.length} features found
          </span>
        </div>

        <div className="feature-grid">
          {featureList.map(({ key, label, nav, icon }) => (
            <button
              key={key}
              className={`feature-card ${features[key] ? "feature-found" : "feature-missing"}`}
              onClick={() => onNav(nav)}
            >
              <span className="feature-icon">{icon}</span>
              <span className="feature-label">{label}</span>
              <span className={`feature-status-dot ${features[key] ? "dot-green" : "dot-grey"}`} />
            </button>
          ))}
        </div>
      </div>

      {/* AI summary */}
      {aiAnalysis?.summary && (
        <div className="ai-summary-card">
          <div className="ai-summary-header">
            <span className="ai-badge">✦ AI INSIGHTS</span>
            <span className={`priority-badge priority-${(aiAnalysis.priority || "").toLowerCase()}`}>
              {aiAnalysis.priority}
            </span>
          </div>
          <p>{aiAnalysis.summary}</p>
        </div>
      )}
    </div>
  );
}

// ============================================================
// SECTION: MENU
// ============================================================

function MenuSection({ menu, toast }) {
  const [search, setSearch] = useState("");
  const [activeCategory, setActiveCategory] = useState("all");

  const categories = menu.categories || [];
  const hasItems = categories.length > 0;

  const allItems = categories.flatMap((cat) =>
    (cat.items || []).map((item) => ({ ...item, category: cat.name }))
  );

  const filteredCategories = categories.map((cat) => ({
    ...cat,
    items: (cat.items || []).filter((item) => {
      const q = search.toLowerCase();
      if (!q) return true;
      return (
        (item.name || "").toLowerCase().includes(q) ||
        (item.description || "").toLowerCase().includes(q)
      );
    }),
  })).filter((cat) =>
    activeCategory === "all" || cat.name === activeCategory
  ).filter((cat) => !search || cat.items.length > 0);

  return (
    <div className="section">
      <SectionHeading
        eyebrow="MENU"
        title="Restaurant Menu"
        description={
          hasItems
            ? `${allItems.length} items extracted across ${categories.length} categories.`
            : "Menu extraction results from the scanned website."
        }
      />

      {hasItems && (
        <div className="menu-controls">
          <div className="search-wrap">
            <span className="search-icon">⌕</span>
            <input
              type="text"
              className="search-input"
              placeholder="Search menu items..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            {search && (
              <button className="search-clear" onClick={() => setSearch("")}>
                ✕
              </button>
            )}
          </div>

          <div className="category-tabs">
            <button
              className={activeCategory === "all" ? "cat-tab active" : "cat-tab"}
              onClick={() => setActiveCategory("all")}
            >
              All ({allItems.length})
            </button>
            {categories.map((cat) => (
              <button
                key={cat.name}
                className={activeCategory === cat.name ? "cat-tab active" : "cat-tab"}
                onClick={() => setActiveCategory(cat.name)}
              >
                {cat.name} ({cat.items?.length || 0})
              </button>
            ))}
          </div>
        </div>
      )}

      {!hasItems ? (
        <div>
          <EmptyState
            icon="🍽"
            message="Menu information could not be extracted from this website."
            detail={
              menu.menu_links?.length
                ? "Menu page links were detected — visit them to view the menu."
                : "The website may use a dynamic menu system or PDF that the scanner cannot read."
            }
          />
          {menu.menu_links?.length > 0 && (
            <div className="link-list">
              <span className="mini-label">DETECTED MENU LINKS</span>
              {menu.menu_links.map((link, i) => (
                <a key={i} href={link} target="_blank" rel="noreferrer" className="link-item">
                  {link} ↗
                </a>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="menu-sections">
          {filteredCategories.map((cat, ci) => (
            <div key={`${cat.name}-${ci}`} className="menu-category-block">
              <div className="category-header">
                <h3>{cat.name}</h3>
                <span className="item-badge">{cat.items?.length || 0} items</span>
                {cat.source && (
                  <span className="source-badge">{cat.source}</span>
                )}
              </div>

              {cat.items?.length > 0 ? (
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Item Name</th>
                        <th>Description</th>
                        <th>Price</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cat.items.map((item, ii) => (
                        <tr key={ii}>
                          <td className="row-num">{ii + 1}</td>
                          <td className="item-name">
                            <strong>{item.name || "—"}</strong>
                          </td>
                          <td className="item-desc">
                            {item.description || <span className="muted">No description</span>}
                          </td>
                          <td className="item-price">
                            {item.price ? (
                              <span className="price-tag">{item.price}</span>
                            ) : (
                              <span className="muted">—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : cat.raw_content ? (
                <div className="raw-text-block">
                  <span className="mini-label">RAW CONTENT (unstructured)</span>
                  <p>{cat.raw_content.slice(0, 2000)}</p>
                </div>
              ) : (
                <p className="muted" style={{ padding: "12px 0" }}>No items found in this category.</p>
              )}
            </div>
          ))}

          {search && filteredCategories.length === 0 && (
            <EmptyState icon="⌕" message={`No results for "${search}"`} />
          )}
        </div>
      )}

      {menu.source_url && (
        <div className="source-note">
          <span>Source: </span>
          <a href={menu.source_url} target="_blank" rel="noreferrer">
            {menu.source_url}
          </a>
          {menu.source_method && (
            <span className="badge" style={{ marginLeft: 8 }}>{menu.source_method}</span>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================
// SECTION: CONTACT
// ============================================================

function ContactSection({ contact, navigation, toast }) {
  const phones = contact.phones || [];
  const emails = contact.emails || [];
  const contactLinks = (contact.contact_page_links || navigation?.contact_links || []);

  return (
    <div className="section">
      <SectionHeading
        eyebrow="CONTACT"
        title="Contact Information"
        description="Phone numbers, email addresses and contact pages detected from the website."
      />

      <div className="contact-blocks">
        {/* Phone */}
        <div className="contact-block">
          <div className="contact-block-header">
            <span className="contact-icon">📞</span>
            <h3>Phone Numbers</h3>
          </div>
          {phones.length > 0 ? (
            <div className="contact-items">
              {phones.map((phone, i) => (
                <div key={i} className="contact-item">
                  <a href={`tel:${phone.replace(/\s/g, "")}`} className="contact-value phone-link">
                    {phone}
                  </a>
                  <CopyBtn text={phone} toast={(m, t) => toast(m, t)} />
                </div>
              ))}
            </div>
          ) : (
            <p className="not-available">Not available / Could not be extracted</p>
          )}
        </div>

        {/* Email */}
        <div className="contact-block">
          <div className="contact-block-header">
            <span className="contact-icon">✉</span>
            <h3>Email Addresses</h3>
          </div>
          {emails.length > 0 ? (
            <div className="contact-items">
              {emails.map((email, i) => (
                <div key={i} className="contact-item">
                  <a href={`mailto:${email}`} className="contact-value email-link">
                    {email}
                  </a>
                  <CopyBtn text={email} toast={(m, t) => toast(m, t)} />
                </div>
              ))}
            </div>
          ) : (
            <p className="not-available">Not available / Could not be extracted</p>
          )}
        </div>

        {/* Contact Page */}
        <div className="contact-block">
          <div className="contact-block-header">
            <span className="contact-icon">🔗</span>
            <h3>Contact Page</h3>
          </div>
          {contactLinks.length > 0 ? (
            <div className="contact-items">
              {contactLinks.map((link, i) => (
                <div key={i} className="contact-item">
                  <a href={link} target="_blank" rel="noreferrer" className="contact-value">
                    {link}
                  </a>
                </div>
              ))}
            </div>
          ) : (
            <p className="not-available">Not available / Could not be extracted</p>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================
// SECTION: LOCATION
// ============================================================

function LocationSection({ location, contact, toast }) {
  const primaryAddress = location.primary_address || contact.addresses?.[0];
  const allAddresses = location.all_addresses || contact.addresses || [];
  const mapLink = location.map_link;

  return (
    <div className="section">
      <SectionHeading
        eyebrow="LOCATION"
        title="Business Location"
        description="Address and location information discovered from the website."
      />

      {primaryAddress ? (
        <div className="location-card">
          <div className="location-pin">📍</div>
          <div className="location-info">
            <span className="mini-label">PRIMARY ADDRESS</span>
            <h3>{primaryAddress}</h3>
            <div className="location-actions">
              <CopyBtn text={primaryAddress} toast={(m, t) => toast(m, t)} />
              {mapLink && (
                <a
                  href={mapLink}
                  target="_blank"
                  rel="noreferrer"
                  className="btn btn-primary"
                >
                  📍 Open in Google Maps
                </a>
              )}
            </div>
          </div>
          {location.source && (
            <span className="source-badge">{location.source}</span>
          )}
        </div>
      ) : (
        <EmptyState
          icon="⌖"
          message="Address not available / Could not be extracted"
          detail="The scanner could not detect a business address from this website."
        />
      )}

      {allAddresses.length > 1 && (
        <div className="all-addresses">
          <span className="mini-label">ALL DETECTED ADDRESSES</span>
          {allAddresses.map((addr, i) => (
            <div key={i} className="address-row">
              <span>{addr}</span>
              <div className="address-actions">
                <CopyBtn text={addr} toast={(m, t) => toast(m, t)} />
                <a
                  href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(addr)}`}
                  target="_blank"
                  rel="noreferrer"
                  className="btn btn-sm"
                >
                  Maps ↗
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================================
// SECTION: OPENING HOURS
// ============================================================

function HoursSection({ openingHours }) {
  const hours = openingHours.hours || [];

  return (
    <div className="section">
      <SectionHeading
        eyebrow="OPENING HOURS"
        title="Business Hours"
        description="Operating hours detected from the website or structured data."
      />

      {hours.length > 0 ? (
        <div className="hours-card">
          <div className="hours-source">
            <span className="mini-label">SOURCE</span>
            <span className="badge">{openingHours.source || "Detected"}</span>
          </div>
          <div className="hours-list">
            {hours.map((hour, i) => (
              <div key={i} className="hours-row">
                <span className="hours-day-icon">🕐</span>
                <span>{hour}</span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <EmptyState
          icon="🕐"
          message="Opening hours not available / Could not be extracted"
          detail="The scanner could not detect opening hours from this website. Check the website directly or contact the business."
        />
      )}
    </div>
  );
}

// ============================================================
// SECTION: RESERVATIONS
// ============================================================

function ReservationSection({ reservations }) {
  const links = reservations.reservation_links || [];
  const platforms = reservations.booking_platforms || [];

  return (
    <div className="section">
      <SectionHeading
        eyebrow="RESERVATIONS"
        title="Table Reservations"
        description="Reservation and booking information detected from the website."
      />

      <div className="feature-status-card">
        <div className={`status-indicator ${reservations.available ? "status-found" : "status-not-found"}`}>
          <span>{reservations.available ? "✓" : "—"}</span>
        </div>
        <div>
          <h3>
            {reservations.available
              ? "Reservation functionality detected"
              : "Reservations not detected / Could not be extracted"}
          </h3>
          <p>
            {reservations.available
              ? (reservations.booking_info || "Reservation capability was found during the scan.")
              : "The scanner could not detect reservation functionality on this website."}
          </p>
        </div>
      </div>

      {platforms.length > 0 && (
        <div className="platforms-block">
          <span className="mini-label">BOOKING PLATFORMS DETECTED</span>
          <div className="platform-list">
            {platforms.map((p, i) => (
              <span key={i} className="platform-badge">{p}</span>
            ))}
          </div>
        </div>
      )}

      {links.length > 0 && (
        <div className="link-list">
          <span className="mini-label">RESERVATION LINKS</span>
          {links.map((link, i) => (
            <a key={i} href={link} target="_blank" rel="noreferrer" className="link-item">
              {link} ↗
            </a>
          ))}
        </div>
      )}

      {!reservations.available && (
        <div className="note-card">
          <strong>Note:</strong> "Not detected" means the scanner could not find reservation
          functionality in the scanned content. The website may still offer reservations
          through phone or other means.
        </div>
      )}
    </div>
  );
}

// ============================================================
// SECTION: ORDERING
// ============================================================

function OrderingSection({ ordering }) {
  const links = ordering.ordering_links || [];
  const platforms = ordering.ordering_platforms || [];

  return (
    <div className="section">
      <SectionHeading
        eyebrow="ONLINE ORDERING"
        title="Online Ordering & Delivery"
        description="Online ordering and delivery information detected from the website."
      />

      <div className="feature-status-card">
        <div className={`status-indicator ${ordering.available ? "status-found" : "status-not-found"}`}>
          <span>{ordering.available ? "✓" : "—"}</span>
        </div>
        <div>
          <h3>
            {ordering.available
              ? "Online ordering / delivery detected"
              : "Online ordering not detected / Could not be extracted"}
          </h3>
          <p>
            {ordering.available
              ? (ordering.delivery_info || "Online ordering capability was found during the scan.")
              : "The scanner could not detect online ordering on this website."}
          </p>
        </div>
      </div>

      {platforms.length > 0 && (
        <div className="platforms-block">
          <span className="mini-label">ORDERING PLATFORMS DETECTED</span>
          <div className="platform-list">
            {platforms.map((p, i) => (
              <span key={i} className="platform-badge">{p}</span>
            ))}
          </div>
        </div>
      )}

      {links.length > 0 && (
        <div className="link-list">
          <span className="mini-label">ORDERING LINKS</span>
          {links.map((link, i) => (
            <a key={i} href={link} target="_blank" rel="noreferrer" className="link-item">
              {link} ↗
            </a>
          ))}
        </div>
      )}

      {!ordering.available && (
        <div className="note-card">
          <strong>Note:</strong> "Not detected" means the scanner could not find ordering
          functionality in the scanned content. Check the website directly for ordering options.
        </div>
      )}
    </div>
  );
}

// ============================================================
// SECTION: SOCIAL MEDIA
// ============================================================

const SOCIAL_PLATFORMS = [
  { key: "facebook", label: "Facebook", icon: "f", color: "#1877F2" },
  { key: "instagram", label: "Instagram", icon: "In", color: "#E1306C" },
  { key: "tiktok", label: "TikTok", icon: "tt", color: "#000000" },
  { key: "youtube", label: "YouTube", icon: "▶", color: "#FF0000" },
  { key: "twitter", label: "Twitter/X", icon: "𝕏", color: "#000000" },
  { key: "x", label: "X", icon: "𝕏", color: "#000000" },
  { key: "linkedin", label: "LinkedIn", icon: "in", color: "#0077B5" },
  { key: "pinterest", label: "Pinterest", icon: "P", color: "#E60023" },
  { key: "snapchat", label: "Snapchat", icon: "👻", color: "#FFFC00" },
  { key: "other", label: "Other", icon: "◎", color: "#888" },
];

function SocialSection({ social, toast }) {
  const activePlatforms = SOCIAL_PLATFORMS.filter(
    (p) => (social[p.key] || []).length > 0
  );

  return (
    <div className="section">
      <SectionHeading
        eyebrow="SOCIAL MEDIA"
        title="Social Media Profiles"
        description="Social media accounts discovered from the scanned website."
      />

      {activePlatforms.length === 0 ? (
        <EmptyState
          icon="◎"
          message="No social media profiles detected / Could not be extracted"
          detail="The scanner did not find any social media links on this website."
        />
      ) : (
        <div className="social-grid">
          {activePlatforms.map(({ key, label, icon, color }) => {
            const links = social[key] || [];
            return (
              <div key={key} className="social-card">
                <div className="social-icon" style={{ background: color }}>
                  {icon}
                </div>
                <div className="social-info">
                  <h3>{label}</h3>
                  {links.map((link, i) => (
                    <div key={i} className="social-link-row">
                      <a href={link} target="_blank" rel="noreferrer" className="social-url">
                        {link.replace("https://", "").replace("http://", "").slice(0, 50)}
                        {link.length > 55 ? "..." : ""}
                      </a>
                      <CopyBtn text={link} toast={(m, t) => toast(m, t)} />
                    </div>
                  ))}
                </div>
                <a
                  href={links[0]}
                  target="_blank"
                  rel="noreferrer"
                  className="social-visit-btn"
                >
                  Visit ↗
                </a>
              </div>
            );
          })}
        </div>
      )}

      <div className="table-wrap" style={{ marginTop: 24 }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Platform</th>
              <th>Status</th>
              <th>URL</th>
            </tr>
          </thead>
          <tbody>
            {SOCIAL_PLATFORMS.filter(p => p.key !== "other").map(({ key, label }) => {
              const links = social[key] || [];
              return (
                <tr key={key}>
                  <td><strong>{label}</strong></td>
                  <td>
                    <span className={links.length > 0 ? "badge-found" : "badge-missing"}>
                      {links.length > 0 ? "✓ Detected" : "Not detected"}
                    </span>
                  </td>
                  <td>
                    {links.length > 0 ? (
                      <a href={links[0]} target="_blank" rel="noreferrer" className="table-link">
                        {links[0]}
                      </a>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ============================================================
// SECTION: ABOUT
// ============================================================

function AboutSection({ restaurant, about, content }) {
  return (
    <div className="section">
      <SectionHeading
        eyebrow="ABOUT"
        title="About the Restaurant"
        description="Business description and background content extracted from the website."
      />

      {about.about_text || restaurant.description ? (
        <div className="about-card">
          <h3>{restaurant.name || "Restaurant"}</h3>
          <p>{about.about_text || restaurant.description}</p>
        </div>
      ) : (
        <EmptyState
          icon="ⓘ"
          message="About content not available / Could not be extracted"
          detail="The scanner could not find a dedicated about/story section on this website."
        />
      )}

      {about.about_links?.length > 0 && (
        <div className="link-list">
          <span className="mini-label">ABOUT PAGE LINKS</span>
          {about.about_links.map((link, i) => (
            <a key={i} href={link} target="_blank" rel="noreferrer" className="link-item">
              {link} ↗
            </a>
          ))}
        </div>
      )}

      <div className="content-stats">
        <StatCard label="Word Count" value={(content.word_count || 0).toLocaleString()} />
      </div>
    </div>
  );
}

// ============================================================
// SECTION: WEBSITE / SEO
// ============================================================

function WebsiteSection({ facts, seo, content }) {
  return (
    <div className="section">
      <SectionHeading
        eyebrow="WEBSITE / SEO"
        title="Website & SEO Information"
        description="Search engine and content information detected during the scan."
      />

      <div className="info-grid">
        <InfoRow label="Page Title" value={seo.title} />
        <InfoRow label="Title Length" value={seo.title_length ? `${seo.title_length} chars` : null} />
        <InfoRow label="Meta Description" value={seo.meta_description} multiline />
        <InfoRow
          label="Meta Desc. Length"
          value={seo.meta_description_length ? `${seo.meta_description_length} chars` : null}
        />
        <InfoRow label="Canonical URL" value={seo.canonical_url} link />
        <InfoRow label="Language" value={facts.restaurant?.language} />
        <InfoRow label="Word Count" value={(content.word_count || 0).toLocaleString()} />
        <InfoRow label="H1 Count" value={seo.h1_count} />
        <InfoRow label="Structured Data" value={seo.structured_data_count || 0} />
        <InfoRow label="Mobile Viewport" value={seo.mobile_viewport ? "Yes" : "No"} />
      </div>

      {seo.h1?.length > 0 && (
        <div className="seo-headings">
          <span className="mini-label">H1 HEADINGS</span>
          <ul className="headings-list">
            {seo.h1.map((h, i) => (
              <li key={i}>{h}</li>
            ))}
          </ul>
        </div>
      )}

      {seo.h2?.length > 0 && (
        <div className="seo-headings" style={{ marginTop: 16 }}>
          <span className="mini-label">H2 HEADINGS (first 10)</span>
          <ul className="headings-list">
            {seo.h2.slice(0, 10).map((h, i) => (
              <li key={i}>{h}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ============================================================
// SECTION: TECHNICAL
// ============================================================

function TechnicalSection({ technical, facts }) {
  return (
    <div className="section">
      <SectionHeading
        eyebrow="TECHNICAL"
        title="Technical Information"
        description="Technical characteristics detected during the website scan."
      />

      <div className="technical-grid">
        <TechnicalCard title="HTTPS / SSL" value={technical.https} />
        <TechnicalCard title="Mobile Responsive" value={technical.mobile_responsive} />
        <TechnicalCard title="JavaScript App" value={technical.javascript_app} />
        <TechnicalCard title="Structured Data" value={technical.structured_data} />
        <TechnicalCard title="Favicon" value={technical.favicon} />
        <TechnicalCard title="Canonical URL" value={technical.canonical} />
      </div>

      <div className="info-grid" style={{ marginTop: 24 }}>
        <InfoRow label="HTTP Status" value={facts.status_code} />
        <InfoRow label="Scanner Method" value={facts.scanner_method} />
        <InfoRow
          label="Response Time"
          value={
            facts.response_time_ms
              ? `${Math.round(facts.response_time_ms)} ms`
              : null
          }
        />
        <InfoRow label="HTML Size" value={facts.scanner?.html_size ? `${Math.round(facts.scanner.html_size / 1024)} KB` : null} />
        <InfoRow label="Word Count" value={facts.scanner?.word_count?.toLocaleString()} />
        <InfoRow label="Images" value={facts.scanner?.image_count} />
        <InfoRow label="Internal Links" value={facts.scanner?.internal_link_count} />
        <InfoRow label="External Links" value={facts.scanner?.external_link_count} />
      </div>
    </div>
  );
}

// ============================================================
// SECTION: AI INSIGHTS
// ============================================================

function AISection({ analysis }) {
  if (!analysis) {
    return (
      <div className="section">
        <EmptyState icon="✦" message="AI insights are not available." />
      </div>
    );
  }

  return (
    <div className="section">
      <SectionHeading
        eyebrow="AI INSIGHTS"
        title="AI Analysis"
        description="AI-generated observations and recommendations based on the extracted website data."
      />

      <div className="ai-score-row">
        <div className="ai-score-ring">
          <svg viewBox="0 0 100 100" className="score-svg">
            <circle cx="50" cy="50" r="40" fill="none" stroke="var(--border)" strokeWidth="8" />
            <circle
              cx="50"
              cy="50"
              r="40"
              fill="none"
              stroke="var(--accent)"
              strokeWidth="8"
              strokeDasharray={`${(analysis.score || 0) * 2.51} 251`}
              strokeLinecap="round"
              transform="rotate(-90 50 50)"
            />
          </svg>
          <div className="score-center">
            <strong>{analysis.score || 0}</strong>
            <small>/100</small>
          </div>
        </div>
        <div className="ai-score-info">
          <h3>Overall Quality Score</h3>
          <span className={`priority-badge priority-${(analysis.priority || "").toLowerCase()}`}>
            {analysis.priority || "Unknown"} Priority
          </span>
          {analysis.summary && <p className="ai-summary">{analysis.summary}</p>}
          {analysis.ai_status && (
            <span className="ai-status-badge">{analysis.ai_status}</span>
          )}
        </div>
      </div>

      <div className="ai-cards-grid">
        {analysis.strengths?.length > 0 && (
          <InsightCard
            title="✓ Strengths"
            items={analysis.strengths}
            variant="success"
          />
        )}
        <InsightCard
          title="⚠ Problems"
          items={analysis.problems}
          variant="warning"
        />
        <InsightCard
          title="✗ Missing Features"
          items={analysis.missing_features}
          variant="danger"
        />
        <InsightCard
          title="→ Recommendations"
          items={analysis.recommendations}
          variant="info"
        />
      </div>
    </div>
  );
}

// ============================================================
// SECTION: SCAN DETAILS
// ============================================================

function ScanDetailsSection({ facts, result }) {
  return (
    <div className="section">
      <SectionHeading
        eyebrow="SCAN DETAILS"
        title="Scan Information"
        description="Technical details about this scan session."
      />

      <div className="info-grid">
        <InfoRow label="Requested URL" value={facts.requested_url} link />
        <InfoRow label="Final URL" value={facts.final_url} link />
        <InfoRow label="Scan Timestamp" value={result.audit_timestamp ? new Date(result.audit_timestamp).toLocaleString() : null} />
        <InfoRow label="Scan Duration" value={result.scan_duration_ms ? `${(result.scan_duration_ms / 1000).toFixed(2)}s` : null} />
        <InfoRow label="Scanner Method" value={facts.scanner_method} />
        <InfoRow label="HTTP Status" value={facts.status_code} />
        <InfoRow label="Response Time" value={facts.response_time_ms ? `${Math.round(facts.response_time_ms)} ms` : null} />
        <InfoRow label="HTML Size" value={facts.scanner?.html_size ? `${Math.round(facts.scanner.html_size / 1024)} KB` : null} />
        <InfoRow label="Word Count" value={facts.scanner?.word_count} />
        <InfoRow label="Images Found" value={facts.scanner?.image_count} />
        <InfoRow label="Internal Links" value={facts.scanner?.internal_link_count} />
        <InfoRow label="External Links" value={facts.scanner?.external_link_count} />
      </div>

      {result.report_file && (
        <div className="note-card" style={{ marginTop: 16 }}>
          <strong>Server Report:</strong> {result.report_file}
        </div>
      )}
    </div>
  );
}

// ============================================================
// SECTION: REPORT
// ============================================================

function ReportSection({ result, toast }) {
  const facts = result?.automatic_facts || {};
  const aiAnalysis = result?.ai_analysis || {};
  const restaurant = facts.restaurant || {};

  const downloadJSON = () => {
    const blob = new Blob([JSON.stringify(result, null, 2)], {
      type: "application/json",
    });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `foodintel-report-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
    toast("JSON report downloaded!", "success");
  };

  const downloadHTML = () => {
    const contact = facts.contact || {};
    const menu = facts.menu || {};
    const social = facts.social_media || {};
    const seo = facts.seo || {};
    const technical = facts.technical || {};
    const hours = facts.opening_hours || {};
    const reservations = facts.reservations || {};
    const ordering = facts.ordering || {};

    const menuHtml = menu.categories?.length
      ? menu.categories.map(cat => `
        <h3>${cat.name || "Category"}</h3>
        ${cat.items?.length ? `
        <table border="1" cellpadding="6" cellspacing="0" style="width:100%;border-collapse:collapse">
          <tr><th>#</th><th>Item</th><th>Description</th><th>Price</th></tr>
          ${cat.items.map((item, i) => `
            <tr>
              <td>${i + 1}</td>
              <td><strong>${item.name || "—"}</strong></td>
              <td>${item.description || "—"}</td>
              <td>${item.price || "—"}</td>
            </tr>
          `).join("")}
        </table>` : `<p>${cat.raw_content || "No items extracted."}</p>`}
      `).join("<hr>")
      : "<p>Menu information could not be extracted.</p>";

    const socialHtml = Object.entries(social)
      .filter(([, links]) => links.length > 0)
      .map(([platform, links]) => `<li><strong>${platform}:</strong> <a href="${links[0]}">${links[0]}</a></li>`)
      .join("");

    const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FoodIntel Report — ${restaurant.name || result.website}</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; color: #111; }
  h1 { color: #b45309; border-bottom: 3px solid #b45309; padding-bottom: 12px; }
  h2 { color: #333; margin-top: 32px; border-bottom: 1px solid #ddd; padding-bottom: 6px; }
  h3 { color: #555; }
  table { width: 100%; border-collapse: collapse; margin: 12px 0; }
  th, td { padding: 8px 12px; border: 1px solid #ddd; text-align: left; }
  th { background: #f5f5f5; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; background: #f0f0f0; font-size: 12px; }
  .ok { color: #15803d; }
  .warn { color: #b45309; }
  .meta { color: #666; font-size: 13px; }
  .ai-section { background: #fff7ed; border: 1px solid #fed7aa; padding: 16px; border-radius: 8px; margin: 16px 0; }
  ul { padding-left: 20px; }
  li { margin: 4px 0; }
  hr { margin: 24px 0; border: none; border-top: 1px solid #eee; }
</style>
</head>
<body>
<h1>🍽 FoodIntel Restaurant Intelligence Report</h1>
<p class="meta">Generated: ${new Date().toLocaleString()} | Platform: FoodIntel AI Food Website Auditor</p>

<h2>Restaurant Overview</h2>
<table>
  <tr><td><strong>Name</strong></td><td>${restaurant.name || "Not extracted"}</td></tr>
  <tr><td><strong>Website</strong></td><td><a href="${result.website}">${result.website}</a></td></tr>
  <tr><td><strong>Description</strong></td><td>${restaurant.description || "Not extracted"}</td></tr>
  <tr><td><strong>Language</strong></td><td>${restaurant.language || "Not detected"}</td></tr>
  <tr><td><strong>Scan Date</strong></td><td>${result.audit_timestamp ? new Date(result.audit_timestamp).toLocaleString() : "—"}</td></tr>
  <tr><td><strong>HTTP Status</strong></td><td>${facts.status_code || "—"}</td></tr>
</table>

<h2>Contact Information</h2>
<table>
  <tr><td><strong>Phone</strong></td><td>${contact.phones?.join(", ") || "Not available / Could not be extracted"}</td></tr>
  <tr><td><strong>Email</strong></td><td>${contact.emails?.join(", ") || "Not available / Could not be extracted"}</td></tr>
  <tr><td><strong>Address</strong></td><td>${contact.addresses?.join(" | ") || "Not available / Could not be extracted"}</td></tr>
</table>

<h2>Opening Hours</h2>
${hours.hours?.length ? `<ul>${hours.hours.map(h => `<li>${h}</li>`).join("")}</ul>` : "<p>Not available / Could not be extracted</p>"}

<h2>Menu</h2>
${menuHtml}

<h2>Reservations</h2>
<p><strong>Available:</strong> ${reservations.available ? "Yes — detected" : "Not detected"}</p>
${reservations.booking_platforms?.length ? `<p><strong>Platforms:</strong> ${reservations.booking_platforms.join(", ")}</p>` : ""}
${reservations.reservation_links?.length ? `<p><strong>Links:</strong> ${reservations.reservation_links.map(l => `<a href="${l}">${l}</a>`).join(", ")}</p>` : ""}

<h2>Online Ordering</h2>
<p><strong>Available:</strong> ${ordering.available ? "Yes — detected" : "Not detected"}</p>
${ordering.ordering_platforms?.length ? `<p><strong>Platforms:</strong> ${ordering.ordering_platforms.join(", ")}</p>` : ""}
${ordering.ordering_links?.length ? `<p><strong>Links:</strong> ${ordering.ordering_links.map(l => `<a href="${l}">${l}</a>`).join(", ")}</p>` : ""}

<h2>Social Media</h2>
${socialHtml ? `<ul>${socialHtml}</ul>` : "<p>No social media profiles detected / Could not be extracted</p>"}

<h2>SEO Information</h2>
<table>
  <tr><td><strong>Page Title</strong></td><td>${seo.title || "Not detected"}</td></tr>
  <tr><td><strong>Meta Description</strong></td><td>${seo.meta_description || "Not detected"}</td></tr>
  <tr><td><strong>H1 Count</strong></td><td>${seo.h1_count || 0}</td></tr>
  <tr><td><strong>Structured Data</strong></td><td>${seo.structured_data_count || 0} blocks</td></tr>
  <tr><td><strong>Mobile Viewport</strong></td><td>${seo.mobile_viewport ? "Yes" : "No"}</td></tr>
</table>

<h2>Technical Information</h2>
<table>
  <tr><td><strong>HTTPS</strong></td><td>${technical.https ? "✓ Yes" : "✗ No"}</td></tr>
  <tr><td><strong>Mobile Responsive</strong></td><td>${technical.mobile_responsive ? "✓ Yes" : "✗ No"}</td></tr>
  <tr><td><strong>JavaScript App</strong></td><td>${technical.javascript_app ? "Yes" : "No"}</td></tr>
  <tr><td><strong>Structured Data</strong></td><td>${technical.structured_data ? "Yes" : "No"}</td></tr>
  <tr><td><strong>Favicon</strong></td><td>${technical.favicon ? "Yes" : "No"}</td></tr>
  <tr><td><strong>Scanner Method</strong></td><td>${facts.scanner_method || "—"}</td></tr>
  <tr><td><strong>Response Time</strong></td><td>${facts.response_time_ms ? `${Math.round(facts.response_time_ms)} ms` : "—"}</td></tr>
</table>

<h2>AI Intelligence Insights</h2>
<div class="ai-section">
  <p><strong>Overall Score:</strong> ${aiAnalysis.score || 0}/100 | <strong>Priority:</strong> ${aiAnalysis.priority || "—"}</p>
  ${aiAnalysis.summary ? `<p>${aiAnalysis.summary}</p>` : ""}
  ${aiAnalysis.strengths?.length ? `<h3>Strengths</h3><ul>${aiAnalysis.strengths.map(s => `<li>${s}</li>`).join("")}</ul>` : ""}
  ${aiAnalysis.problems?.length ? `<h3>Problems</h3><ul>${aiAnalysis.problems.map(p => `<li>${p}</li>`).join("")}</ul>` : ""}
  ${aiAnalysis.missing_features?.length ? `<h3>Missing Features</h3><ul>${aiAnalysis.missing_features.map(f => `<li>${f}</li>`).join("")}</ul>` : ""}
  ${aiAnalysis.recommendations?.length ? `<h3>Recommendations</h3><ul>${aiAnalysis.recommendations.map(r => `<li>${r}</li>`).join("")}</ul>` : ""}
</div>

<hr>
<p class="meta">Report generated by FoodIntel AI Food Website Intelligence Platform. 
Data was extracted automatically from publicly accessible website content. 
"Not detected" means the information was not found in the scanned content — it may still exist on the website.</p>
</body>
</html>`;

    const blob = new Blob([html], { type: "text/html" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `foodintel-report-${new Date().toISOString().slice(0, 10)}.html`;
    link.click();
    URL.revokeObjectURL(link.href);
    toast("HTML report downloaded!", "success");
  };

  return (
    <div className="section">
      <SectionHeading
        eyebrow="REPORT"
        title="Download Report"
        description="Export the complete scan data and intelligence report."
      />

      <div className="report-grid">
        <button className="report-card" onClick={downloadJSON} id="download-json">
          <div className="report-icon">{ }</div>
          <span className="report-icon-text">{"{}"}</span>
          <strong>Download JSON</strong>
          <small>Complete raw scan data — all extracted fields</small>
        </button>

        <button className="report-card" onClick={downloadHTML} id="download-html">
          <div className="report-icon">{ }</div>
          <span className="report-icon-text">{"</>"}</span>
          <strong>Download HTML Report</strong>
          <small>Professional formatted report — save as PDF from browser</small>
        </button>

        <button
          className="report-card"
          onClick={() => {
            window.print();
          }}
          id="print-report"
        >
          <div className="report-icon">{ }</div>
          <span className="report-icon-text">🖨</span>
          <strong>Print / Save PDF</strong>
          <small>Use browser print dialog to save as PDF</small>
        </button>
      </div>

      <div className="note-card" style={{ marginTop: 24 }}>
        <strong>Data Accuracy Note:</strong> All information was automatically extracted from
        the publicly accessible content of the scanned website at the time of the scan.
        "Not available / Could not be extracted" means the scanner did not find that
        information — it may still exist on the website. Never use this data as a
        definitive business listing.
      </div>
    </div>
  );
}

// ============================================================
// SHARED COMPONENTS
// ============================================================

function SectionHeading({ eyebrow, title, description }) {
  return (
    <div className="section-heading">
      <span className="eyebrow">{eyebrow}</span>
      <h2>{title}</h2>
      {description && <p>{description}</p>}
    </div>
  );
}

function StatCard({ label, value, green }) {
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <strong className={green ? "text-success" : ""}>{value ?? "—"}</strong>
    </div>
  );
}

function InfoRow({ label, value, link, multiline }) {
  if (!value && value !== 0) {
    return (
      <div className="info-row">
        <span className="info-label">{label}</span>
        <span className="info-value muted">Not detected</span>
      </div>
    );
  }
  return (
    <div className="info-row">
      <span className="info-label">{label}</span>
      <span className={`info-value ${multiline ? "multiline" : ""}`}>
        {link ? (
          <a href={String(value)} target="_blank" rel="noreferrer" className="table-link">
            {String(value)}
          </a>
        ) : (
          String(value)
        )}
      </span>
    </div>
  );
}

function TechnicalCard({ title, value }) {
  return (
    <div className="technical-item">
      <div className={`tech-check ${value ? "tech-found" : "tech-missing"}`}>
        {value ? "✓" : "✗"}
      </div>
      <div>
        <span className="tech-title">{title}</span>
        <strong className={value ? "text-success" : "text-muted"}>
          {value ? "Detected" : "Not detected"}
        </strong>
      </div>
    </div>
  );
}

function InsightCard({ title, items, variant }) {
  const list = Array.isArray(items) ? items : [];
  return (
    <div className={`insight-card insight-${variant}`}>
      <h3>{title}</h3>
      {list.length ? (
        <ul>
          {list.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">No items in this category.</p>
      )}
    </div>
  );
}

function EmptyState({ icon, message, detail }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">{icon || "⌁"}</div>
      <h3>{message}</h3>
      {detail && <p>{detail}</p>}
    </div>
  );
}