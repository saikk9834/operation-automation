import { useState, useEffect, useRef, useCallback } from "react";

const API = (import.meta.env.VITE_API_URL ?? "") + "/api";

// ── Hooks ─────────────────────────────────────────────────────────────────────

function useSettings(setForm) {
  useEffect(() => {
    fetch(`${API}/settings`)
      .then((r) => r.json())
      .then((cfg) =>
        setForm({
          all_in_one_path:  cfg.all_in_one_path  ?? "",
          destination_path: cfg.destination_path ?? "",
          recipient_email:  cfg.recipient_email  ?? "",
          cc_email:         cfg.cc_email         ?? "",
        })
      )
      .catch(() => {});
  }, [setForm]);
}

function useAutoSave(form) {
  const [saved, setSaved] = useState(false);
  const timerRef = useRef(null);
  useEffect(() => {
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(async () => {
      try {
        await fetch(`${API}/settings`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(form),
        });
        setSaved(true);
        setTimeout(() => setSaved(false), 1800);
      } catch (_) {}
    }, 900);
    return () => clearTimeout(timerRef.current);
  }, [form]);
  return saved;
}

function usePipeline() {
  const [status, setStatus]   = useState("idle");
  const [log, setLog]         = useState([]);
  const [errorMsg, setErrorMsg] = useState("");
  const pollRef = useRef(null);

  const stopPolling = () => clearInterval(pollRef.current);

  const startPolling = useCallback(() => {
    let seen = 0;
    pollRef.current = setInterval(async () => {
      try {
        const r = await fetch(`${API}/status`);
        const s = await r.json();
        if (s.log.length > seen) { setLog([...s.log]); seen = s.log.length; }
        if (!s.running) {
          stopPolling();
          if (s.error)    { setErrorMsg(s.error); setStatus("error"); }
          else if (s.done) setStatus("done");
        }
      } catch (_) {}
    }, 800);
  }, []);

  const run = useCallback(async (form) => {
    setStatus("running"); setLog([]); setErrorMsg("");
    try {
      await fetch(`${API}/reset`, { method: "POST" });
      const r = await fetch(`${API}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await r.json();
      if (!r.ok) { setErrorMsg(data.error ?? "Server error"); setStatus("error"); return; }
      startPolling();
    } catch (_) {
      setErrorMsg("Cannot reach backend. Is api.py running on port 8000?");
      setStatus("error");
    }
  }, [startPolling]);

  useEffect(() => () => stopPolling(), []);
  return { status, log, errorMsg, run };
}

// ── FolderPicker modal ────────────────────────────────────────────────────────

function FolderPicker({ onSelect, onClose }) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState("");

  const load = useCallback(async (path) => {
    setLoading(true); setError("");
    try {
      const url = `${API}/browse` + (path ? `?path=${encodeURIComponent(path)}` : "");
      const r = await fetch(url);
      if (!r.ok) { const e = await r.json(); throw new Error(e.error); }
      setData(await r.json());
    } catch (e) {
      setError(e.message || "Failed to load directory");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Close on Escape
  useEffect(() => {
    const h = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  return (
    <div style={s.overlay} onClick={onClose}>
      <div style={s.modal} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div style={s.modalHeader}>
          <span style={s.modalTitle}>Select Folder</span>
          <button onClick={onClose} style={s.closeBtn}>✕</button>
        </div>

        {/* Breadcrumbs */}
        {data && (
          <div style={s.breadcrumbs}>
            {data.breadcrumbs.map((b, i) => (
              <span key={b.path} style={s.breadcrumbWrap}>
                {i > 0 && <span style={s.breadSep}>/</span>}
                <button
                  style={s.breadBtn}
                  onClick={() => load(b.path)}
                >
                  {b.name}
                </button>
              </span>
            ))}
          </div>
        )}

        {/* Current path display */}
        {data && (
          <div style={s.currentPath}>{data.current}</div>
        )}

        {/* Directory listing */}
        <div style={s.dirList}>
          {loading && <div style={s.dimText}>Loading…</div>}
          {error   && <div style={s.errorText}>{error}</div>}
          {!loading && !error && data && data.entries.length === 0 && (
            <div style={s.dimText}>No sub-folders here</div>
          )}
          {!loading && data && data.entries.map((entry) => (
            <div
              key={entry.path}
              style={s.dirEntry}
              onClick={() => entry.has_children ? load(entry.path) : null}
              onDoubleClick={() => load(entry.path)}
            >
              <span style={s.folderIcon}>📁</span>
              <span style={{ ...s.entryName, ...(entry.has_children ? {} : s.entryLeaf) }}>
                {entry.name}
              </span>
              {entry.has_children && <span style={s.chevron}>›</span>}
            </div>
          ))}
        </div>

        {/* Footer */}
        <div style={s.modalFooter}>
          <span style={s.selectedLabel}>
            {data ? <><strong style={{ color: "#e4e6ef" }}>Selected:</strong> {data.current}</> : ""}
          </span>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={onClose} style={s.cancelBtn}>Cancel</button>
            <button
              onClick={() => data && onSelect(data.current)}
              disabled={!data}
              style={s.selectBtn}
            >
              Select This Folder
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── PathField — text input + browse button ────────────────────────────────────

function PathField({ id, label, value, onChange, disabled, note }) {
  const [pickerOpen, setPickerOpen] = useState(false);

  const paste = async () => {
    try {
      const t = await navigator.clipboard.readText();
      onChange(id, t.trim());
    } catch (_) { alert("Clipboard access denied — paste the path manually."); }
  };

  return (
    <div style={s.field}>
      <label style={s.label} htmlFor={id}>{label}</label>
      <div style={s.inputRow}>
        <input
          id={id}
          type="text"
          value={value}
          placeholder="Click Browse or paste a path…"
          disabled={disabled}
          autoComplete="off"
          onChange={(e) => onChange(id, e.target.value)}
          style={{ ...s.input, ...s.inputMultiBtn, ...(disabled ? s.inputDisabled : {}) }}
        />
        <button onClick={paste} disabled={disabled} style={s.iconBtn} title="Paste from clipboard">⎘</button>
        <button
          onClick={() => setPickerOpen(true)}
          disabled={disabled}
          style={{ ...s.iconBtn, ...s.browseBtn }}
          title="Browse server folders"
        >
          Browse
        </button>
      </div>
      {note && <span style={s.note}>{note}</span>}

      {pickerOpen && (
        <FolderPicker
          onSelect={(path) => { onChange(id, path); setPickerOpen(false); }}
          onClose={() => setPickerOpen(false)}
        />
      )}
    </div>
  );
}

// ── EmailField ─────────────────────────────────────────────────────────────────

function EmailField({ id, label, value, onChange, disabled, optional }) {
  return (
    <div style={s.field}>
      <label style={s.label} htmlFor={id}>
        {label}{optional && <span style={s.optTag}> optional</span>}
      </label>
      <input
        id={id}
        type="email"
        value={value}
        placeholder="email@example.com"
        disabled={disabled}
        autoComplete="off"
        onChange={(e) => onChange(id, e.target.value)}
        style={{ ...s.input, ...(disabled ? s.inputDisabled : {}) }}
      />
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function LogPanel({ lines }) {
  const ref = useRef(null);
  useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, [lines]);
  if (!lines.length) return null;
  return (
    <div ref={ref} style={s.logPanel}>
      {lines.map((line, i) => (
        <div key={i} style={{
          ...s.logLine,
          ...(line.startsWith("✅") || line.startsWith("✓") ? s.logSuccess : {}),
          ...(line.startsWith("❌") || line.startsWith("Error") ? s.logError : {}),
        }}>{line}</div>
      ))}
    </div>
  );
}

function Banner({ type, message }) {
  if (!message) return null;
  return (
    <div style={{ ...s.banner, ...(type === "success" ? s.bannerSuccess : s.bannerError) }}>
      <span>{type === "success" ? "✓" : "✕"}</span>
      <span>{message}</span>
    </div>
  );
}

function Spinner() { return <span style={s.spinner} />; }

// ── Main App ──────────────────────────────────────────────────────────────────

export default function App() {
  const [form, setForm] = useState({
    all_in_one_path: "", destination_path: "", recipient_email: "", cc_email: "",
  });

  const setFormCb = useCallback((next) => setForm(next), []);
  useSettings(setFormCb);

  const saved = useAutoSave(form);
  const { status, log, errorMsg, run } = usePipeline();
  const isRunning = status === "running";

  const handleChange = (id, val) => setForm((prev) => ({ ...prev, [id]: val }));

  const handleRun = () => {
    const missing = [];
    if (!form.all_in_one_path.trim())  missing.push("All-in-One Folder");
    if (!form.destination_path.trim()) missing.push("Destination Folder");
    if (!form.recipient_email.trim())  missing.push("Recipient Email");
    if (missing.length) { alert(`Please fill in: ${missing.join(", ")}`); return; }
    run(form);
  };

  return (
    <div style={s.page}>
      <div style={s.shell}>
        <header style={s.header}>
          <div style={s.tag}><span style={s.tagLine} /> Automation System</div>
          <h1 style={s.h1}>Operation <span style={s.accent}>Automation</span></h1>
          <p style={s.subtitle}>Configure paths and credentials, then run the fulfillment pipeline.</p>
        </header>

        <div style={s.card}>
          {/* Paths */}
          <div style={s.sectionLabel}><span>File Paths</span><span style={s.sectionLine} /></div>
          <div style={s.fieldGroup}>
            <PathField
              id="all_in_one_path" label="All-in-One Folder"
              value={form.all_in_one_path} onChange={handleChange} disabled={isRunning}
              note="Server-side path to the folder containing all artwork files."
            />
            <PathField
              id="destination_path" label="Destination Folder"
              value={form.destination_path} onChange={handleChange} disabled={isRunning}
              note="Server-side path where sorted files and the final ZIP will be written."
            />
          </div>

          <div style={s.divider} />

          {/* Email */}
          <div style={s.sectionLabel}><span>Notifications</span><span style={s.sectionLine} /></div>
          <div style={s.fieldGroup}>
            <EmailField id="recipient_email" label="Recipient Email" value={form.recipient_email} onChange={handleChange} disabled={isRunning} />
            <EmailField id="cc_email" label="CC Email" value={form.cc_email} onChange={handleChange} disabled={isRunning} optional />
          </div>

          <div style={s.saveRow}>
            <span style={{ ...s.saveInd, opacity: saved ? 1 : 0 }}>✓ Settings saved</span>
          </div>

          <button onClick={handleRun} disabled={isRunning}
            style={{ ...s.runBtn, ...(isRunning ? s.runBtnRunning : {}) }}>
            {isRunning ? <><Spinner /> Running…</> : "Run Fulfillment Pipeline"}
          </button>

          <LogPanel lines={log} />
          {status === "done"  && <Banner type="success" message="Pipeline completed. Email notification sent." />}
          {status === "error" && <Banner type="error"   message={errorMsg || "An error occurred. Check the log."} />}
        </div>

        <footer style={s.footer}>OPERATION AUTOMATION · INTERNAL TOOL</footer>
      </div>
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const s = {
  page: {
    minHeight: "100vh", background: "#0b0c0f",
    backgroundImage: `
      radial-gradient(ellipse 80% 50% at 50% -10%, rgba(232,255,90,.07) 0%, transparent 60%),
      repeating-linear-gradient(0deg,transparent,transparent 39px,rgba(255,255,255,.018) 39px,rgba(255,255,255,.018) 40px),
      repeating-linear-gradient(90deg,transparent,transparent 39px,rgba(255,255,255,.018) 39px,rgba(255,255,255,.018) 40px)`,
    display: "flex", justifyContent: "center",
    padding: "40px 20px 80px", fontFamily: "'DM Mono', monospace", color: "#e4e6ef",
  },
  shell:    { width: "100%", maxWidth: 680, display: "flex", flexDirection: "column" },
  header:   { paddingBottom: 36 },
  tag:      { fontFamily: "'DM Mono',monospace", fontSize: 10, letterSpacing: ".18em", textTransform: "uppercase", color: "#e8ff5a", marginBottom: 10, display: "flex", alignItems: "center", gap: 8 },
  tagLine:  { display: "inline-block", width: 18, height: 1, background: "#e8ff5a" },
  h1:       { fontFamily: "'Syne',sans-serif", fontSize: "clamp(28px,5vw,42px)", fontWeight: 800, lineHeight: 1.05, letterSpacing: "-.02em", color: "#fff" },
  accent:   { color: "#e8ff5a" },
  subtitle: { marginTop: 8, fontSize: 12, color: "#7a7f94", letterSpacing: ".04em" },
  card:     { background: "#13151a", border: "1px solid #232530", borderRadius: 12, padding: 32 },
  sectionLabel: { fontSize: 10, letterSpacing: ".14em", textTransform: "uppercase", color: "#4a4f60", marginBottom: 20, display: "flex", alignItems: "center", gap: 10 },
  sectionLine:  { flex: 1, height: 1, background: "#232530" },
  fieldGroup:   { display: "flex", flexDirection: "column", gap: 18, marginBottom: 28 },
  field:        { display: "flex", flexDirection: "column", gap: 6 },
  label:        { fontSize: 11, letterSpacing: ".1em", textTransform: "uppercase", color: "#7a7f94" },
  optTag:       { color: "#4a4f60", fontSize: 9, textTransform: "none", letterSpacing: 0, marginLeft: 4 },
  inputRow:     { display: "flex" },
  input:        { flex: 1, background: "#0b0c0f", border: "1px solid #232530", borderRadius: 6, padding: "10px 14px", fontFamily: "'DM Mono',monospace", fontSize: 13, color: "#e4e6ef", outline: "none" },
  inputMultiBtn:{ borderRadius: "6px 0 0 6px" },
  inputDisabled:{ opacity: 0.4, cursor: "not-allowed" },
  iconBtn:      { background: "#232530", border: "1px solid #232530", borderLeft: "none", borderRadius: 0, color: "#7a7f94", padding: "0 12px", cursor: "pointer", fontSize: 14, display: "flex", alignItems: "center", justifyContent: "center" },
  browseBtn:    { borderRadius: "0 6px 6px 0", fontSize: 11, letterSpacing: ".06em", padding: "0 14px", color: "#e4e6ef", whiteSpace: "nowrap" },
  note:         { fontSize: 10, color: "#4a4f60", marginTop: 2 },
  divider:      { height: 1, background: "#232530", margin: "24px 0" },
  saveRow:      { display: "flex", justifyContent: "flex-end", marginTop: -8, marginBottom: 12 },
  saveInd:      { fontSize: 10, color: "#4a4f60", letterSpacing: ".08em", transition: "opacity .4s" },
  runBtn:       { width: "100%", padding: "14px 24px", background: "#e8ff5a", color: "#0b0c0f", border: "none", borderRadius: 6, fontFamily: "'Syne',sans-serif", fontSize: 15, fontWeight: 700, letterSpacing: ".04em", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 },
  runBtnRunning:{ background: "#232530", color: "#7a7f94", cursor: "not-allowed" },
  spinner:      { display: "inline-block", width: 14, height: 14, border: "2px solid currentColor", borderTopColor: "transparent", borderRadius: "50%", animation: "spin .7s linear infinite" },
  logPanel:     { marginTop: 16, background: "#0b0c0f", border: "1px solid #232530", borderRadius: 6, padding: 16, maxHeight: 260, overflowY: "auto" },
  logLine:      { fontSize: 12, lineHeight: 1.7, color: "#7a7f94", padding: "1px 0" },
  logSuccess:   { color: "#5affca" },
  logError:     { color: "#ff5a6e" },
  banner:       { display: "flex", alignItems: "center", gap: 10, padding: "12px 16px", borderRadius: 6, fontSize: 13, marginTop: 16 },
  bannerSuccess:{ background: "rgba(90,255,202,.08)", border: "1px solid rgba(90,255,202,.2)", color: "#5affca" },
  bannerError:  { background: "rgba(255,90,110,.08)", border: "1px solid rgba(255,90,110,.2)", color: "#ff5a6e" },
  footer:       { marginTop: 32, textAlign: "center", fontSize: 10, color: "#4a4f60", letterSpacing: ".1em" },

  // ── Modal ──
  overlay:      { position: "fixed", inset: 0, background: "rgba(0,0,0,.7)", backdropFilter: "blur(4px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 },
  modal:        { background: "#13151a", border: "1px solid #2e3140", borderRadius: 12, width: "min(600px, 94vw)", maxHeight: "80vh", display: "flex", flexDirection: "column", overflow: "hidden", boxShadow: "0 24px 60px rgba(0,0,0,.6)" },
  modalHeader:  { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 20px", borderBottom: "1px solid #232530" },
  modalTitle:   { fontFamily: "'Syne',sans-serif", fontWeight: 700, fontSize: 15, color: "#fff" },
  closeBtn:     { background: "none", border: "none", color: "#7a7f94", cursor: "pointer", fontSize: 16, padding: 4, lineHeight: 1 },
  breadcrumbs:  { display: "flex", flexWrap: "wrap", alignItems: "center", gap: 2, padding: "10px 20px 0", fontSize: 11 },
  breadcrumbWrap:{ display: "flex", alignItems: "center", gap: 2 },
  breadSep:     { color: "#4a4f60", margin: "0 2px" },
  breadBtn:     { background: "none", border: "none", color: "#7a7f94", cursor: "pointer", fontFamily: "'DM Mono',monospace", fontSize: 11, padding: "2px 4px", borderRadius: 3 },
  currentPath:  { padding: "6px 20px 10px", fontSize: 11, color: "#4a4f60", borderBottom: "1px solid #1a1c23", wordBreak: "break-all" },
  dirList:      { flex: 1, overflowY: "auto", padding: "8px 12px" },
  dirEntry:     { display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", borderRadius: 6, cursor: "pointer", transition: "background .15s" },
  folderIcon:   { fontSize: 14, flexShrink: 0 },
  entryName:    { flex: 1, fontSize: 13, color: "#c8cad4", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  entryLeaf:    { color: "#4a4f60" },
  chevron:      { color: "#4a4f60", fontSize: 18, flexShrink: 0 },
  dimText:      { padding: "20px 10px", color: "#4a4f60", fontSize: 12, textAlign: "center" },
  errorText:    { padding: "20px 10px", color: "#ff5a6e", fontSize: 12, textAlign: "center" },
  modalFooter:  { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "14px 20px", borderTop: "1px solid #232530", flexWrap: "wrap" },
  selectedLabel:{ fontSize: 11, color: "#4a4f60", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  cancelBtn:    { background: "#1e2028", border: "1px solid #232530", color: "#7a7f94", borderRadius: 6, padding: "8px 16px", cursor: "pointer", fontFamily: "'DM Mono',monospace", fontSize: 12 },
  selectBtn:    { background: "#e8ff5a", border: "none", color: "#0b0c0f", borderRadius: 6, padding: "8px 18px", cursor: "pointer", fontFamily: "'Syne',sans-serif", fontWeight: 700, fontSize: 12 },
};