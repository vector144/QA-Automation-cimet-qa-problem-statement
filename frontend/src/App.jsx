import React, { useState, useEffect, useRef } from "react";
import {
  Shield,
  Play,
  Pause,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  FileDown,
  FileSpreadsheet,
  RotateCcw,
  Sparkles,
  Volume2,
  User,
  MapPin,
  Mail,
  Phone,
  Calendar,
  CheckSquare,
  Edit3,
  Search,
  Sun,
  Moon,
  Clock,
  ExternalLink,
  History,
  FileText,
  DollarSign,
  AlertCircle
} from "lucide-react";

const API_BASE = "http://localhost:8000";

export default function App() {
  // Theme: Light mode by default
  const [theme, setTheme] = useState("light");

  // Navigation Tabs
  const [activeTab, setActiveTab] = useState("overview"); // 'overview' | 'factcheck' | 'disclosures' | 'transcript' | 'history'

  // Data States
  const [leads, setLeads] = useState([]);
  const [selectedLeadId, setSelectedLeadId] = useState("");
  const [leadDetail, setLeadDetail] = useState(null);
  const [scoringResults, setScoringResults] = useState(null);
  const [transcriptTurns, setTranscriptTurns] = useState([]);
  const [overrideHistory, setOverrideHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [auditRunning, setAuditRunning] = useState(false);
  const [transcribeRunning, setTranscribeRunning] = useState(false);

  // Audio Playback State — driven by real <audio> element
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1.0);
  const [audioError, setAudioError] = useState(null);
  const audioRef = useRef(null);           // Real <audio> element
  const transcriptContainerRef = useRef(null);

  // Transcript Search Filter
  const [transcriptSearch, setTranscriptSearch] = useState("");

  // Human Override Modal State
  const [showOverrideModal, setShowOverrideModal] = useState(false);
  const [selectedCheckForOverride, setSelectedCheckForOverride] = useState(null);
  const [overrideStatus, setOverrideStatus] = useState("PASS");
  const [overrideGateStatus, setOverrideGateStatus] = useState("");
  const [overrideJustification, setOverrideJustification] = useState("");
  const [overrideReviewerName, setOverrideReviewerName] = useState("Lead QA Auditor");
  const [overrideSubmitting, setOverrideSubmitting] = useState(false);

  // Apply Theme to DOM
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  };

  // 1. Initial Load: Fetch Leads
  useEffect(() => {
    loadLeads();
  }, []);

  const loadLeads = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/leads`);
      if (res.ok) {
        const data = await res.json();
        setLeads(data);
        if (data.length > 0) {
          const preferred = data.find((l) => l.id === "lead-audio-3613793") || data[0];
          setSelectedLeadId(preferred.id);
        }
      }
    } catch (err) {
      console.error("Failed to load leads:", err);
    } finally {
      setLoading(false);
    }
  };

  // 2. When Selected Lead Changes
  useEffect(() => {
    if (!selectedLeadId) return;
    loadLeadData(selectedLeadId);
  }, [selectedLeadId]);

  const loadLeadData = async (id) => {
    try {
      // 1. Fetch Lead Details
      let currentGateStatus = "PENDING";
      const leadRes = await fetch(`${API_BASE}/api/leads/${id}`);
      if (leadRes.ok) {
        const lead = await leadRes.json();
        setLeadDetail(lead);
        currentGateStatus = lead.gate_status;
        if (lead.call_duration_sec) {
          setDuration(lead.call_duration_sec);
        }
      }

      // 2. Fetch Latest Scoring Results (only if lead has completed scoring)
      if (currentGateStatus && currentGateStatus !== "PENDING") {
        const res = await fetch(`${API_BASE}/api/scoring/results/${id}`);
        if (res.ok) {
          const results = await res.json();
          setScoringResults(results);
        } else {
          setScoringResults(null);
        }
      } else {
        setScoringResults(null);
      }

      // 3. Fetch Transcript Turns
      loadTranscriptTurns(id);

      // 4. Fetch Human Override History
      loadOverrideHistory(id);
    } catch (err) {
      console.error("Error loading lead data:", err);
    }
  };

  const loadTranscriptTurns = async (id) => {
    try {
      const res = await fetch(`${API_BASE}/api/leads/${id}/transcript`);
      if (res.ok) {
        const data = await res.json();
        if (data.turns && data.turns.length > 0) {
          setTranscriptTurns(data.turns);
          return;
        }
      }
    } catch (e) {
      console.warn("Could not fetch real transcript turns:", e);
    }
  };

  const loadOverrideHistory = async (id) => {
    try {
      const res = await fetch(`${API_BASE}/api/reviews/${id}/history`);
      if (res.ok) {
        const data = await res.json();
        setOverrideHistory(data);
      }
    } catch (err) {
      console.warn("Could not load override history:", err);
    }
  };

  // 3. Real Audio Playback Engine — sync state from <audio> element
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const onTimeUpdate = () => setCurrentTime(audio.currentTime);
    const onDurationChange = () => setDuration(audio.duration || 0);
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);
    const onEnded = () => { setIsPlaying(false); };
    const onError = () => setAudioError("Audio file could not be loaded.");

    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("durationchange", onDurationChange);
    audio.addEventListener("play", onPlay);
    audio.addEventListener("pause", onPause);
    audio.addEventListener("ended", onEnded);
    audio.addEventListener("error", onError);

    return () => {
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("durationchange", onDurationChange);
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("pause", onPause);
      audio.removeEventListener("ended", onEnded);
      audio.removeEventListener("error", onError);
    };
  }, []);

  // Update playback speed on the real audio element
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.playbackRate = playbackSpeed;
    }
  }, [playbackSpeed]);

  // When the selected lead changes, reset playback state
  // (the <audio> element itself is remounted via key={selectedLeadId})
  useEffect(() => {
    setAudioError(null);
    setCurrentTime(0);
    setDuration(0);
    setIsPlaying(false);
  }, [selectedLeadId]);

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) {
      audio.play().catch((e) => setAudioError("Playback blocked: " + e.message));
    } else {
      audio.pause();
    }
  };

  const seekTo = (timestamp_ms, tabToOpen = null) => {
    const sec = timestamp_ms ? timestamp_ms / 1000 : 0;
    if (audioRef.current) {
      audioRef.current.currentTime = sec;
      audioRef.current.play().catch(() => { });
    }
    setCurrentTime(sec);
    setIsPlaying(true);
    if (tabToOpen) setActiveTab(tabToOpen);

    setTimeout(() => {
      const activeEl = document.querySelector(".transcript-bubble.active-highlight");
      if (activeEl && transcriptContainerRef.current) {
        activeEl.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }, 150);
  };

  const formatTime = (secs) => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  // Auto-scroll transcript container to keep active speech bubble visible
  useEffect(() => {
    if (!isPlaying || activeTab !== "transcript") return;
    const activeEl = document.querySelector(".transcript-bubble.active-highlight");
    if (activeEl && transcriptContainerRef.current) {
      activeEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [currentTime, isPlaying, activeTab]);

  // 4. Run Compliance Scoring Audit
  const handleRunAudit = async () => {
    try {
      setAuditRunning(true);
      const res = await fetch(`${API_BASE}/api/scoring/run/${selectedLeadId}`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        setScoringResults(data);
        // Refresh lead details for updated gate status
        const leadRes = await fetch(`${API_BASE}/api/leads/${selectedLeadId}`);
        if (leadRes.ok) setLeadDetail(await leadRes.json());
      }
    } catch (err) {
      console.error("Audit execution error:", err);
    } finally {
      setAuditRunning(false);
    }
  };

  // 5. Submit QA Supervisor Override
  const handleSubmitOverride = async (e) => {
    e.preventDefault();
    if (!overrideJustification || overrideJustification.trim().length < 5) {
      alert("A substantive audit justification note (minimum 5 characters) is mandatory.");
      return;
    }

    try {
      setOverrideSubmitting(true);
      const payload = {
        check_id: selectedCheckForOverride ? selectedCheckForOverride.check_id : null,
        reviewer_id: "auditor-01",
        reviewer_name: overrideReviewerName,
        new_status: overrideStatus,
        gate_status_override: overrideGateStatus || null,
        justification: overrideJustification,
      };

      const res = await fetch(`${API_BASE}/api/reviews/${selectedLeadId}/override`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        setShowOverrideModal(false);
        setOverrideJustification("");
        // Reload all data
        loadLeadData(selectedLeadId);
      } else {
        const err = await res.json();
        alert(`Override failed: ${err.detail || "Server error"}`);
      }
    } catch (err) {
      console.error("Override submission error:", err);
    } finally {
      setOverrideSubmitting(false);
    }
  };

  // 6. Trigger Groq Whisper transcription for the current lead
  const handleTranscribe = async () => {
    if (!selectedLeadId) return;
    try {
      setTranscribeRunning(true);
      // First seed leads if needed
      await fetch(`${API_BASE}/api/audio/seed-leads`, { method: "POST" });
      // Then trigger transcription
      const res = await fetch(`${API_BASE}/api/audio/transcribe/${selectedLeadId}`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        alert(`✅ Transcription complete! ${data.turns_count} turns, ${Math.round(data.duration_sec)}s duration.`);
        loadLeadData(selectedLeadId);
      } else {
        const err = await res.json();
        alert(`❌ Transcription failed: ${err.detail}`);
      }
    } catch (err) {
      alert(`❌ Network error: ${err.message}`);
    } finally {
      setTranscribeRunning(false);
    }
  };

  // Checks categorization
  const checkResults = scoringResults?.check_results || [];
  const verbatimChecks = checkResults.filter((c) => c.check_type === "VERBATIM");
  const factualChecks = checkResults.filter((c) => c.check_type === "FACTUAL");
  const crm = leadDetail?.crm_fields || {};

  // Gatekeeper status helpers
  const gateStatus = leadDetail?.gate_status || scoringResults?.gate_decision || "PENDING";
  const isGatePassed = gateStatus === "PASSED";
  const isGateFailed = gateStatus === "FAILED";
  const isGateReview = gateStatus === "NEEDS_REVIEW" || gateStatus === "PENDING";

  // Filtered transcript turns
  const filteredTurns = transcriptTurns.filter((turn) => {
    if (!transcriptSearch) return true;
    return turn.text.toLowerCase().includes(transcriptSearch.toLowerCase()) ||
      turn.speaker.toLowerCase().includes(transcriptSearch.toLowerCase());
  });

  return (
    <div className="app-container">
      {/* ── PERSISTENT HIDDEN AUDIO ELEMENT (always rendered for stable ref) ── */}
      <audio
        key={selectedLeadId}
        ref={audioRef}
        src={leadDetail?.recording_url ? `${API_BASE}${leadDetail.recording_url}` : undefined}
        preload="metadata"
        style={{ display: "none" }}
        onEnded={() => setIsPlaying(false)}
      />

      {/* ── TOP HEADER NAVBAR (MINIMAL & SLEEK) ─────────────── */}
      <header className="top-nav">
        <div className="nav-left">
          <div className="brand-badge">
            <span className="brand-yellow-mark">
              <Shield size={13} />
              <span>CIMET</span>
            </span>
            <span className="brand-title">QA Compliance Auditor</span>
            <span className="brand-version">v1.0</span>
          </div>

          <div className="v-divider" />

          <div className="live-indicator">
            <span className="pulse-dot" />
            <span>Auditor Live</span>
          </div>

          <div className="v-divider" />

          <div className="lead-selector-wrap">
            <User size={13} style={{ color: "var(--steel)" }} />
            <select
              value={selectedLeadId}
              onChange={(e) => setSelectedLeadId(e.target.value)}
              className="lead-select"
            >
              {leads.map((lead) => (
                <option key={lead.id} value={lead.id}>
                  {lead.recording_url ? "🔊 " : ""}{lead.customer_name || lead.crm_fields?.customer_full_name || lead.id} • {lead.retailer_name || lead.retailer_id}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="nav-right">
          <button
            className="btn btn-secondary"
            style={{ padding: "6px 14px", fontSize: "12px" }}
            onClick={() => window.open(`${API_BASE}/api/export/csv`, "_blank")}
            title="Download CSV Audit Report"
          >
            <FileSpreadsheet size={14} />
            <span>CSV</span>
          </button>

          {/* <button
            className="btn btn-secondary"
            style={{ padding: "6px 14px", fontSize: "12px" }}
            onClick={() => window.open(`${API_BASE}/api/export/transcript-pdf?lead_id=${selectedLeadId}`, "_blank")}
            title="Preview Official Timestamped PDF Transcript"
          >
            <FileText size={14} />
            <span>PDF Transcript</span>
          </button> */}



          <button
            className="btn btn-primary"
            style={{ padding: "6px 16px", fontSize: "12.5px" }}
            onClick={handleRunAudit}
            disabled={auditRunning}
          >
            {auditRunning ? <RotateCcw size={14} className="spin" /> : <Sparkles size={14} />}
            <span>{auditRunning ? "Auditing..." : "Re-Run Scoring"}</span>
          </button>

          <button className="btn-theme" onClick={toggleTheme} title={`Switch to ${theme === 'light' ? 'Dark' : 'Light'} Mode`}>
            {theme === "light" ? <Moon size={15} /> : <Sun size={15} />}
          </button>
        </div>
      </header>

      {/* ── MINIMAL PILL TAB NAVIGATION BAR ────────────────── */}
      <nav className="tabs-nav-bar">
        <button
          className={`tab-btn ${activeTab === "overview" ? "active" : ""}`}
          onClick={() => setActiveTab("overview")}
        >
          <CheckSquare size={15} />
          <span>Overview</span>
        </button>

        <button
          className={`tab-btn ${activeTab === "factcheck" ? "active" : ""}`}
          onClick={() => setActiveTab("factcheck")}
        >
          <DollarSign size={15} />
          <span>Fact Check</span>
          <span className="tab-count">{factualChecks.length}</span>
        </button>

        <button
          className={`tab-btn ${activeTab === "disclosures" ? "active" : ""}`}
          onClick={() => setActiveTab("disclosures")}
        >
          <FileText size={15} />
          <span>Disclosures</span>
          <span className="tab-count">{verbatimChecks.length}</span>
        </button>

        <button
          className={`tab-btn ${activeTab === "transcript" ? "active" : ""}`}
          onClick={() => setActiveTab("transcript")}
        >
          <Volume2 size={15} />
          <span>Audio & Transcript</span>
          <span className="tab-count">{transcriptTurns.length}</span>
        </button>

        <button
          className={`tab-btn ${activeTab === "history" ? "active" : ""}`}
          onClick={() => setActiveTab("history")}
        >
          <History size={15} />
          <span>Audit History</span>
          <span className="tab-count">{overrideHistory.length}</span>
        </button>
      </nav>

      {/* ── MAIN CONTENT TABS CONTAINER ─────────────────────── */}
      <main className="main-content">

        {/* ══════════════════════════════════════════════════════════════════════
            TAB 1: OVERVIEW & COMPLIANCE GATING
           ══════════════════════════════════════════════════════════════════════ */}
        {activeTab === "overview" && (
          <div>
            {/* Gate Status Hero Banner */}
            <div className={`gate-banner ${isGatePassed ? "passed" : isGateFailed ? "failed" : "review"}`}>
              <div className="gate-banner-left">
                <div className="gate-banner-icon">
                  {isGatePassed && <CheckCircle2 size={24} color="var(--pass)" />}
                  {isGateFailed && <XCircle size={24} color="var(--fail)" />}
                  {isGateReview && <AlertTriangle size={24} color="var(--review)" />}
                </div>
                <div>
                  <div className="gate-title">
                    <span>Regulatory Gate Decision: {gateStatus}</span>
                    {isGateFailed && <span className="badge badge-critical">SALE PROVISIONING BLOCKED</span>}
                    {isGatePassed && <span className="badge badge-pass">SALE APPROVED</span>}
                  </div>
                  <div className="gate-desc">
                    {isGateFailed && "Critical regulatory compliance check failed. Australian legal standards prohibit passing this sale to the retailer until rectified."}
                    {isGatePassed && "All mandatory ACCC, Privacy Act disclosures and CRM factual reconciliation parameters verified successfully."}
                    {isGateReview && "Lead flagged for mandatory supervisor review before provisioning approval."}
                  </div>
                </div>
              </div>

              <button
                className="btn btn-secondary"
                onClick={() => {
                  setSelectedCheckForOverride(null);
                  setOverrideGateStatus(isGateFailed ? "PASSED" : "FAILED");
                  setShowOverrideModal(true);
                }}
              >
                <Edit3 size={14} />
                <span>Override Gate Decision</span>
              </button>
            </div>

            {/* Metric KPI Cards (Miro Pastel Palette) */}
            <div className="stat-cards-grid">
              <div className="card-pastel card-pastel-mint">
                <div className="card-pastel-label">Overall Compliance Score</div>
                <div className="card-pastel-val">
                  {scoringResults ? `${scoringResults.score}%` : "Pending"}
                </div>
                <div className="card-pastel-sub">Min. Passing Threshold: 85%</div>
              </div>

              <div className="card-pastel card-pastel-coral">
                <div className="card-pastel-label">Critical Gate Status</div>
                <div className="card-pastel-val">
                  {checkResults.filter((c) => c.is_critical && c.status === "PASS").length} / {checkResults.filter((c) => c.is_critical).length}
                </div>
                <div className="card-pastel-sub">
                  {checkResults.filter((c) => c.is_critical && c.status === "FAIL").length} Critical Breaches Detected
                </div>
              </div>

              <div className="card-pastel card-pastel-yellow">
                <div className="card-pastel-label">Rulebook Evaluated</div>
                <div className="card-pastel-val" style={{ fontSize: "20px", marginTop: "8px" }}>
                  {scoringResults?.check_library_id || "broadband-v1"}
                </div>
                <div className="card-pastel-sub">Active on Date: {leadDetail?.call_date || "2024-03-15"}</div>
              </div>

              <div className="card-pastel card-pastel-blue">
                <div className="card-pastel-label">Call Duration</div>
                <div className="card-pastel-val" style={{ fontSize: "20px", marginTop: "8px" }}>
                  {formatTime(duration)} ({transcriptTurns.length} turns)
                </div>
                <div className="card-pastel-sub">100% Turn Speech Diarization</div>
              </div>
            </div>

            {/* 2-Column Overview Panels */}
            <div className="grid-2col">
              {/* Call Profile & Lead Details */}
              <div className="panel-card">
                <div className="panel-header">
                  <span className="panel-title">
                    <User size={16} />
                    <span>Customer & Call Profile</span>
                  </span>
                  <span className="badge badge-pass">Lead ID: {selectedLeadId}</span>
                </div>
                <div className="panel-body">
                  <div className="crm-grid">
                    <div className="crm-row">
                      <span className="crm-label">Customer Name</span>
                      <span className="crm-value">{leadDetail?.customer_name || crm.customer_full_name || "Margaret Jenkins"}</span>
                    </div>
                    <div className="crm-row">
                      <span className="crm-label">Retailer</span>
                      <span className="crm-value">{leadDetail?.retailer_name || leadDetail?.retailer_id || "Dodo NBN"}</span>
                    </div>
                    <div className="crm-row">
                      <span className="crm-label">Sales Representative</span>
                      <span className="crm-value">{leadDetail?.agent_name || "Marcus Vance"}</span>
                    </div>
                    <div className="crm-row">
                      <span className="crm-label">Call Date</span>
                      <span className="crm-value">{leadDetail?.call_date || "2024-03-15"}</span>
                    </div>
                    <div className="crm-row">
                      <span className="crm-label">Customer Phone</span>
                      <span className="crm-value">{crm.phone || "0412 345 678"}</span>
                    </div>
                    <div className="crm-row">
                      <span className="crm-label">Customer Email</span>
                      <span className="crm-value">{crm.email || "margaret.jenkins48@gmail.com"}</span>
                    </div>
                    <div className="crm-row" style={{ gridColumn: "span 2" }}>
                      <span className="crm-label">Service Installation Address</span>
                      <span className="crm-value">{crm.service_address || "14/28 Riverview Road, Parramatta NSW 2150"}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* CRM Financial Truth Parameters */}
              <div className="panel-card">
                <div className="panel-header">
                  <span className="panel-title">
                    <DollarSign size={16} />
                    <span>Expected CRM Contract Terms</span>
                  </span>
                  <span style={{ fontSize: "11px", color: "var(--text-dim)" }}>ACCC Required Disclosures</span>
                </div>
                <div className="panel-body">
                  <div className="crm-grid">
                    <div className="crm-row">
                      <span className="crm-label">Introductory Rate</span>
                      <span className="crm-value">${crm.plan_price_intro ?? "42.90"} / mo (First 6 Mos)</span>
                    </div>
                    <div className="crm-row">
                      <span className="crm-label">Standard Ongoing Rate</span>
                      <span className="crm-value">${crm.plan_price_standard ?? "72.90"} / mo</span>
                    </div>
                    <div className="crm-row">
                      <span className="crm-label">Hardware Upfront Cost</span>
                      <span className="crm-value">${crm.modem_upfront_cost ?? "0.00"} (Free Wi-Fi 6 Modem)</span>
                    </div>
                    <div className="crm-row">
                      <span className="crm-label">Modem Delivery SLA</span>
                      <span className="crm-value">{crm.delivery_days || "3 to 5 business days"}</span>
                    </div>
                    <div className="crm-row">
                      <span className="crm-label">Plan Contract Term</span>
                      <span className="crm-value">Month-to-Month (No lock-in contract)</span>
                    </div>
                    <div className="crm-row">
                      <span className="crm-label">NBN Access Technology</span>
                      <span className="crm-value">Fibre to the Premises (FTTP)</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════════
            TAB 2: FACT CHECK & CRM RECONCILIATION
           ══════════════════════════════════════════════════════════════════════ */}
        {activeTab === "factcheck" && (
          <div>
            <div style={{ marginBottom: "16px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <h2 style={{ fontSize: "18px", fontWeight: 700 }}>CRM Factual Cross-Check & Reconciliation</h2>
                <p style={{ fontSize: "13px", color: "var(--text-muted)" }}>
                  Audits spoken verbal commitments against CRM system of record to prevent consumer misrepresentation under Australian Consumer Law.
                </p>
              </div>
            </div>

            <div className="panel-card">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Check Rule</th>
                    <th>CRM Ground Truth</th>
                    <th>Spoken in Call (Evidence)</th>
                    <th>Citation Turn</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {factualChecks.map((chk) => {
                    const isPass = chk.status === "PASS";
                    return (
                      <tr key={chk.id || chk.check_id}>
                        <td>
                          <div style={{ fontWeight: 600 }}>{chk.check_name}</div>
                          <div style={{ fontSize: "11px", color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                            {chk.check_id} {chk.is_critical && "• Critical"}
                          </div>
                        </td>
                        <td>
                          <code style={{ fontFamily: "var(--font-mono)", fontSize: "12px", background: "var(--bg-card-subtle)", padding: "2px 6px", borderRadius: "4px" }}>
                            {chk.expected_value || "—"}
                          </code>
                        </td>
                        <td>
                          <div style={{ maxWidth: "340px", fontSize: "12.5px" }}>
                            {chk.agent_said ? `"${chk.agent_said}"` : <span style={{ color: "var(--fail)", fontStyle: "italic" }}>Not stated / omitted</span>}
                          </div>
                          {chk.reason && (
                            <div style={{ fontSize: "11px", color: "var(--text-dim)", marginTop: "3px" }}>
                              {chk.reason}
                            </div>
                          )}
                        </td>
                        <td>
                          {chk.transcript_turn !== null ? (
                            <span style={{ fontFamily: "var(--font-mono)", fontSize: "12px" }}>
                              Turn {chk.transcript_turn} ({formatTime(chk.timestamp_ms ? chk.timestamp_ms / 1000 : 0)})
                            </span>
                          ) : (
                            <span style={{ color: "var(--text-dim)" }}>None</span>
                          )}
                        </td>
                        <td>
                          <span className={`badge ${isPass ? "badge-pass" : "badge-fail"}`}>
                            {isPass ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
                            <span>{chk.status}</span>
                          </span>
                        </td>
                        <td>
                          <div style={{ display: "flex", gap: "6px" }}>
                            {chk.timestamp_ms !== null && (
                              <button
                                className="btn btn-secondary"
                                style={{ padding: "4px 8px", fontSize: "11.5px" }}
                                onClick={() => seekTo(chk.timestamp_ms, "transcript")}
                                title="Listen to Evidence in Transcript"
                              >
                                <Play size={12} />
                                <span>Seek</span>
                              </button>
                            )}
                            <button
                              className="btn btn-secondary"
                              style={{ padding: "4px 8px", fontSize: "11.5px" }}
                              onClick={() => {
                                setSelectedCheckForOverride(chk);
                                setOverrideStatus(isPass ? "FAIL" : "PASS");
                                setShowOverrideModal(true);
                              }}
                            >
                              <Edit3 size={12} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════════
            TAB 3: MANDATORY DISCLOSURES (TYPE A VERBATIM)
           ══════════════════════════════════════════════════════════════════════ */}
        {activeTab === "disclosures" && (
          <div>
            <div style={{ marginBottom: "16px" }}>
              <h2 style={{ fontSize: "18px", fontWeight: 700 }}>Mandatory Script Disclosures (Verbatim)</h2>
              <p style={{ fontSize: "13px", color: "var(--text-muted)" }}>
                Strict compliance criteria under ACCC and Privacy Act 1988 guidelines. Missing disclosures immediately block sale progression.
              </p>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {verbatimChecks.map((chk) => {
                const isPass = chk.status === "PASS";
                return (
                  <div key={chk.id || chk.check_id} className="check-item-card">
                    <div className="check-item-header">
                      <div className="check-item-title">
                        {isPass ? <CheckCircle2 size={18} color="var(--pass)" /> : <XCircle size={18} color="var(--fail)" />}
                        <span>{chk.check_name}</span>
                        <span className="check-item-id">{chk.check_id}</span>
                        {chk.is_critical && <span className="badge badge-critical">CRITICAL GATE</span>}
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                        <span className={`badge ${isPass ? "badge-pass" : "badge-fail"}`}>
                          {chk.status} ({Math.round((chk.confidence || 1.0) * 100)}% Confidence)
                        </span>
                        <button
                          className="btn btn-secondary"
                          style={{ padding: "4px 10px", fontSize: "12px" }}
                          onClick={() => {
                            setSelectedCheckForOverride(chk);
                            setOverrideStatus(isPass ? "FAIL" : "PASS");
                            setShowOverrideModal(true);
                          }}
                        >
                          <Edit3 size={13} />
                          <span>Override</span>
                        </button>
                      </div>
                    </div>

                    <div className="check-item-body">
                      {chk.agent_said ? (
                        <div className="check-quote-box">
                          "{chk.agent_said}"
                        </div>
                      ) : (
                        <div style={{ color: "var(--fail)", padding: "8px 0", fontStyle: "italic" }}>
                          No matching mandatory disclosure detected in the transcript.
                        </div>
                      )}

                      <div style={{ fontSize: "12.5px", color: "var(--text-muted)" }}>
                        <strong>Evaluation Reason:</strong> {chk.reason}
                      </div>
                    </div>

                    <div className="check-item-footer">
                      <div>
                        {chk.transcript_turn !== null ? (
                          <span>Spoken in Turn {chk.transcript_turn} ({formatTime(chk.timestamp_ms ? chk.timestamp_ms / 1000 : 0)})</span>
                        ) : (
                          <span>No timestamp citation</span>
                        )}
                      </div>

                      {chk.timestamp_ms !== null && (
                        <button
                          className="btn btn-primary"
                          style={{ padding: "4px 12px", fontSize: "12px" }}
                          onClick={() => seekTo(chk.timestamp_ms, "transcript")}
                        >
                          <Play size={13} />
                          <span>Listen to Evidence</span>
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════════
            TAB 4: CALL AUDIO & INTERACTIVE TRANSCRIPT
           ══════════════════════════════════════════════════════════════════════ */}
        {activeTab === "transcript" && (
          <div>
            {/* Audio Scrubber Panel */}
            <div className="audio-player-panel">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <span style={{ fontSize: "13px", fontWeight: 700 }}>Synchronized Call Timeline Engine</span>
                <div style={{ display: "flex", gap: "8px" }}>
                  <button
                    className="btn btn-secondary"
                    style={{ padding: "3px 8px", fontSize: "11px" }}
                    onClick={() => setPlaybackSpeed((s) => (s === 1.0 ? 1.5 : s === 1.5 ? 2.0 : 1.0))}
                  >
                    Speed: {playbackSpeed}x
                  </button>
                  <button
                    className="btn btn-primary"
                    style={{ padding: "3px 10px", fontSize: "11px" }}
                    onClick={handleTranscribe}
                    disabled={transcribeRunning}
                    title="Run Groq Whisper AI transcription on this call's audio file"
                  >
                    {transcribeRunning ? <RotateCcw size={12} className="spin" /> : <Volume2 size={12} />}
                    <span>{transcribeRunning ? "Transcribing..." : "Transcribe Audio"}</span>
                  </button>
                </div>
              </div>

              {/* Audio file status notice */}
              {!leadDetail?.recording_url && (
                <div style={{ padding: "12px", background: "var(--bg-card-subtle)", borderRadius: "8px", marginBottom: "12px", fontSize: "13px", color: "var(--text-muted)" }}>
                  ⚠️ No audio file linked to this lead. Click <strong>Transcribe Audio</strong> above to run Groq Whisper transcription on the call recording.
                </div>
              )}

              {audioError && (
                <div style={{ padding: "10px 14px", background: "#fef2f2", borderRadius: "8px", marginBottom: "12px", fontSize: "13px", color: "#dc2626" }}>
                  ⚠️ {audioError}
                </div>
              )}

              <div className="audio-controls">
                <button className="play-circle-btn" onClick={togglePlay} disabled={!leadDetail?.recording_url}>
                  {isPlaying ? <Pause size={18} /> : <Play size={18} style={{ marginLeft: "2px" }} />}
                </button>

                <span className="audio-time-label">
                  {formatTime(currentTime)} / {formatTime(duration || 0)}
                </span>

                <input
                  type="range"
                  min="0"
                  max={duration || 100}
                  step="0.5"
                  value={currentTime}
                  onChange={(e) => {
                    const val = parseFloat(e.target.value);
                    setCurrentTime(val);
                    if (audioRef.current) audioRef.current.currentTime = val;
                  }}
                  className="timeline-slider"
                />
              </div>
            </div>

            {/* Transcript Filter & Dialogue List */}
            <div style={{ display: "flex", gap: "10px", alignItems: "center", marginBottom: "12px" }}>
              <input
                type="text"
                placeholder="Search transcript (e.g. 'Dodo', 'Parramatta', 'forty two', 'recorded', 'modem')..."
                value={transcriptSearch}
                onChange={(e) => setTranscriptSearch(e.target.value)}
                className="search-pill"
                style={{ flex: 1, marginBottom: 0 }}
              />
              <button
                className="btn btn-secondary"
                style={{ padding: "8px 14px", fontSize: "12px" }}
                onClick={() => window.open(`${API_BASE}/api/export/transcript-pdf?lead_id=${selectedLeadId}`, "_blank")}
                title="Open Official Timestamped PDF Transcript"
              >
                <FileText size={14} />
                <span>View Full PDF</span>
              </button>
              <span style={{ fontSize: "12px", color: "var(--text-muted)", whiteSpace: "nowrap" }}>
                {filteredTurns.length} of {transcriptTurns.length} turns
              </span>
            </div>

            <div className="transcript-box" ref={transcriptContainerRef}>
              {filteredTurns.map((turn) => {
                const turnStartSec = turn.start_ms / 1000;
                const turnEndSec = turn.end_ms / 1000;
                const isActive = currentTime >= turnStartSec && currentTime <= turnEndSec;

                return (
                  <div
                    key={turn.turn_index}
                    className={`transcript-bubble ${isActive ? "active-highlight" : ""}`}
                    onClick={() => seekTo(turn.start_ms)}
                  >
                    <div className="bubble-head">
                      <span className={`speaker-pill ${turn.speaker.toLowerCase()}`}>
                        {turn.speaker === "Agent"
                          ? `Agent (${leadDetail?.agent_name || "Sales Agent"})`
                          : `Customer (${leadDetail?.customer_name || crm?.customer_full_name || "Customer"})`}
                      </span>
                      <span className="turn-timestamp">
                        Turn {turn.turn_index} • {formatTime(turnStartSec)} - {formatTime(turnEndSec)}
                      </span>
                    </div>
                    <div className="bubble-text">{turn.text}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════════
            TAB 5: SUPERVISOR OVERRIDES & HISTORY LOG
           ══════════════════════════════════════════════════════════════════════ */}
        {activeTab === "history" && (
          <div>
            <div style={{ marginBottom: "16px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <h2 style={{ fontSize: "18px", fontWeight: 700 }}>Human QA Auditor Overrides & Audit Log</h2>
                <p style={{ fontSize: "13px", color: "var(--text-muted)" }}>
                  Mandatory regulatory chain of custody for any manual overturning of automated AI compliance verdicts.
                </p>
              </div>

              <button
                className="btn btn-primary"
                onClick={() => {
                  setSelectedCheckForOverride(null);
                  setOverrideGateStatus(isGateFailed ? "PASSED" : "FAILED");
                  setShowOverrideModal(true);
                }}
              >
                <Edit3 size={15} />
                <span>Submit New Override</span>
              </button>
            </div>

            {overrideHistory.length === 0 ? (
              <div className="panel-card" style={{ padding: "40px", textAlign: "center" }}>
                <CheckCircle2 size={32} color="var(--pass)" style={{ margin: "0 auto 12px" }} />
                <h3 style={{ fontSize: "16px", fontWeight: 700 }}>No Human Overrides Recorded</h3>
                <p style={{ fontSize: "13px", color: "var(--text-muted)", marginTop: "4px" }}>
                  All compliance verdicts currently match the automated AI pipeline evaluation.
                </p>
              </div>
            ) : (
              <div className="panel-card">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Override ID</th>
                      <th>Target Rule / Scope</th>
                      <th>Reviewer</th>
                      <th>Status Transition</th>
                      <th>Mandatory Justification</th>
                      <th>Timestamp (UTC)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {overrideHistory.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <code style={{ fontFamily: "var(--font-mono)", fontSize: "12px" }}>{item.id}</code>
                        </td>
                        <td>
                          <span style={{ fontWeight: 600 }}>{item.check_id || "Full Gate Status"}</span>
                        </td>
                        <td>{item.reviewer_name}</td>
                        <td>
                          <span style={{ textDecoration: "line-through", color: "var(--text-dim)", marginRight: "6px" }}>
                            {item.previous_status}
                          </span>
                          <span className={`badge ${item.new_status === "PASS" || item.new_status === "PASSED" ? "badge-pass" : "badge-fail"}`}>
                            {item.new_status}
                          </span>
                        </td>
                        <td>
                          <div style={{ maxWidth: "300px", fontSize: "12.5px" }}>{item.justification}</div>
                        </td>
                        <td style={{ fontSize: "12px", color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                          {item.created_at}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </main>

      {/* ── SUPERVISOR OVERRIDE MODAL ───────────────────────── */}
      {showOverrideModal && (
        <div className="modal-backdrop" onClick={() => setShowOverrideModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <form onSubmit={handleSubmitOverride}>
              <div className="modal-header">
                <div style={{ fontWeight: 700, fontSize: "16px" }}>
                  Supervisor Compliance Override
                </div>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ padding: "4px 8px" }}
                  onClick={() => setShowOverrideModal(false)}
                >
                  ✕
                </button>
              </div>

              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Reviewer / Supervisor Name</label>
                  <input
                    type="text"
                    value={overrideReviewerName}
                    onChange={(e) => setOverrideReviewerName(e.target.value)}
                    required
                    className="form-input"
                  />
                </div>

                {selectedCheckForOverride ? (
                  <div className="form-group">
                    <label className="form-label">Overriding Specific Rule</label>
                    <div style={{ fontSize: "13px", fontWeight: 600 }}>
                      {selectedCheckForOverride.check_name} ({selectedCheckForOverride.check_id})
                    </div>
                    <div style={{ display: "flex", gap: "10px", marginTop: "6px" }}>
                      <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "13px" }}>
                        <input
                          type="radio"
                          name="status"
                          value="PASS"
                          checked={overrideStatus === "PASS"}
                          onChange={() => setOverrideStatus("PASS")}
                        />
                        Mark as PASS
                      </label>
                      <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "13px" }}>
                        <input
                          type="radio"
                          name="status"
                          value="FAIL"
                          checked={overrideStatus === "FAIL"}
                          onChange={() => setOverrideStatus("FAIL")}
                        />
                        Mark as FAIL
                      </label>
                    </div>
                  </div>
                ) : (
                  <div className="form-group">
                    <label className="form-label">Overriding Overall Gate Decision</label>
                    <select
                      value={overrideGateStatus}
                      onChange={(e) => setOverrideGateStatus(e.target.value)}
                      className="form-select"
                    >
                      <option value="PASSED">PASSED (Authorize Sale)</option>
                      <option value="FAILED">FAILED (Block Sale)</option>
                      <option value="NEEDS_REVIEW">NEEDS_REVIEW (Keep in Queue)</option>
                    </select>
                  </div>
                )}

                <div className="form-group">
                  <label className="form-label">
                    Mandatory Audit Justification Note (Min. 5 chars)
                  </label>
                  <textarea
                    rows={4}
                    placeholder="Document exact regulatory or factual basis for this override decision..."
                    value={overrideJustification}
                    onChange={(e) => setOverrideJustification(e.target.value)}
                    required
                    className="form-textarea"
                  />
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowOverrideModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={overrideSubmitting || overrideJustification.trim().length < 5}
                >
                  {overrideSubmitting ? "Submitting..." : "Save Audit Override"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
