"use client";

import React, { useState } from "react";
import {
  CONFLICT_APP,
  CLEAN_APP,
  ApplicationCase,
  DocumentInfo,
  Finding
} from "./data";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  ShieldCheck,
  FileText,
  Building2,
  Scale,
  Search,
  Eye,
  EyeOff,
  History,
  Link as LinkIcon,
  HelpCircle,
  ArrowRight,
  ShieldAlert,
  ChevronDown,
  ChevronRight,
  Send,
  Sparkles,
  Lock,
  Layers,
  Database
} from "lucide-react";

export default function OfficerReviewPage() {
  const [selectedCaseId, setSelectedCaseId] = useState<"conflict" | "clean">("conflict");
  const [currentApp, setCurrentApp] = useState<ApplicationCase>(CONFLICT_APP);
  const [activeDocId, setActiveDocId] = useState<string>("appx_land_deed");
  const [activeFindingId, setActiveFindingId] = useState<string>("f_4a9c0181");
  const [excludedDocIds, setExcludedDocIds] = useState<string[]>([]);
  const [severityFilter, setSeverityFilter] = useState<"all" | "high" | "low">("all");
  const [cleanCollapsed, setCleanCollapsed] = useState<boolean>(true);

  // Officer Flag Actions
  const [flagActions, setFlagActions] = useState<Record<string, { status: "confirmed" | "dismissed"; reason: string }>>({});
  const [actionInputReason, setActionInputReason] = useState<string>("");

  // Final Decision State
  const [decisionModalOpen, setDecisionModalOpen] = useState(false);
  const [ledgerModalOpen, setLedgerModalOpen] = useState(false);
  const [simDrawerOpen, setSimDrawerOpen] = useState(false);
  const [decisionMade, setDecisionMade] = useState<string | null>(null);

  // Switch Case Handler
  const handleCaseSwitch = (caseType: "conflict" | "clean") => {
    setSelectedCaseId(caseType);
    if (caseType === "conflict") {
      setCurrentApp(CONFLICT_APP);
      setActiveDocId("appx_land_deed");
      setActiveFindingId("f_4a9c0181");
    } else {
      setCurrentApp(CLEAN_APP);
      setActiveDocId("clean_form");
      setActiveFindingId("");
    }
    setExcludedDocIds([]);
    setFlagActions({});
    setActionInputReason("");
    setDecisionMade(null);
  };

  // Toggle document exclusion in Impact Simulator
  const toggleExcludeDoc = (docId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExcludedDocIds(prev =>
      prev.includes(docId) ? prev.filter(id => id !== docId) : [...prev, docId]
    );
  };

  // Active Document
  const activeDoc = currentApp.documents.find(d => d.doc_id === activeDocId) || currentApp.documents[0];

  // Active Finding
  const activeFinding = currentApp.findings.find(f => f.finding_id === activeFindingId);

  // Filtered Findings
  const displayedFindings = currentApp.findings.filter(f => {
    // If associated doc is excluded, mark as bypassed in simulator
    const hasActiveDocs = f.doc_ids.some(id => !excludedDocIds.includes(id));
    if (!hasActiveDocs) return false;
    if (severityFilter === "all") return true;
    return f.severity === severityFilter;
  });

  const highSeverityCount = displayedFindings.filter(f => f.severity === "high").length;
  const lowSeverityCount = displayedFindings.filter(f => f.severity === "low").length;

  // Impact Simulation Metrics
  const formExcluded = excludedDocIds.includes("appx_application_form");
  const deedExcluded = excludedDocIds.includes("appx_land_deed");
  const effectiveLandArea = deedExcluded ? (formExcluded ? 0 : 2.5) : 2.1;
  const landRequirementMet = effectiveLandArea >= 2.0;

  // Handle Flag Confirmation/Dismissal
  const handleRecordFlagAction = (type: "confirmed" | "dismissed") => {
    if (!activeFindingId) return;
    if (!actionInputReason.trim()) {
      alert("Please provide a mandatory rationale for the audit trail.");
      return;
    }
    setFlagActions(prev => ({
      ...prev,
      [activeFindingId]: {
        status: type,
        reason: actionInputReason
      }
    }));
    setActionInputReason("");
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Banner & AICTE Header */}
      <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-500 via-orange-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-orange-500/20 font-black text-white text-lg tracking-wider">
              AICTE
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-base tracking-tight text-white">DocVerf</span>
                <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                  Decision-Support
                </span>
                <span className="text-[10px] text-slate-400 hidden sm:inline">Extension-of-Approval (EoA)</span>
              </div>
              <p className="text-xs text-slate-400">
                Rule engine & evidence graph validation • TRD §18 Officer Portal
              </p>
            </div>
          </div>

          {/* Quick Case Switcher & Officer Profile */}
          <div className="flex items-center gap-3">
            {/* Navigation tabs to Digital Twin and Institute Portal */}
            <div className="flex items-center gap-1.5 text-xs">
              <span className="px-2.5 py-1 rounded-md bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 font-semibold">
                Scrutiny
              </span>
              <a
                href="/digital-twin"
                className="px-2.5 py-1 rounded-md text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition font-medium"
              >
                Digital Twin
              </a>
              <a
                href="/portal"
                className="px-2.5 py-1 rounded-md text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition font-medium"
              >
                Institute Portal
              </a>
            </div>

            <div className="h-6 w-px bg-slate-800 hidden md:block"></div>

            <div className="bg-slate-800/80 p-1 rounded-lg border border-slate-700/80 flex items-center gap-1 text-xs">
              <button
                onClick={() => handleCaseSwitch("conflict")}
                className={`px-3 py-1.5 rounded-md font-medium transition-all ${
                  selectedCaseId === "conflict"
                    ? "bg-rose-500/20 text-rose-300 border border-rose-500/40 shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                Sample Defect (5 Flags)
              </button>
              <button
                onClick={() => handleCaseSwitch("clean")}
                className={`px-3 py-1.5 rounded-md font-medium transition-all ${
                  selectedCaseId === "clean"
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                Sample Clean (0 Flags)
              </button>
            </div>

            <div className="h-6 w-px bg-slate-800 hidden md:block"></div>

            <button
              onClick={() => setLedgerModalOpen(true)}
              className="flex items-center gap-1.5 text-xs bg-slate-800/60 hover:bg-slate-800 text-slate-300 border border-slate-700 px-3 py-1.5 rounded-lg transition"
            >
              <Database className="w-3.5 h-3.5 text-indigo-400" />
              <span>Audit Ledger</span>
            </button>

            <div className="flex items-center gap-2 pl-2">
              <div className="w-8 h-8 rounded-full bg-slate-800 border border-indigo-500/30 flex items-center justify-center font-bold text-xs text-indigo-300">
                SM
              </div>
              <div className="hidden lg:block text-left text-xs">
                <div className="font-semibold text-slate-200">S. Mayee</div>
                <div className="text-[10px] text-slate-400">Scrutiny Officer</div>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Application Overview & Priority Bar (FR-14.1) */}
      <section className="bg-slate-900/40 border-b border-slate-800/80 py-4 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
                <Building2 className="w-5 h-5 text-indigo-400" />
                {currentApp.institute_name}
              </h1>
              <span className="text-xs font-mono bg-slate-800 px-2 py-0.5 rounded text-slate-300 border border-slate-700">
                PID: {currentApp.aicte_permanent_id}
              </span>
              <span className={`text-xs px-2.5 py-0.5 rounded-full font-semibold border ${
                currentApp.priority > 0
                  ? "bg-rose-500/10 text-rose-400 border-rose-500/30 animate-pulse"
                  : "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
              }`}>
                Priority Score: {currentApp.priority}
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400">
              <span>App No: <strong className="text-slate-300">{currentApp.application_no}</strong></span>
              <span>•</span>
              <span>Session: <strong className="text-slate-300">{currentApp.academic_year}</strong></span>
              <span>•</span>
              <span>Overall Status: <span className="font-medium text-amber-400">{decisionMade || currentApp.status}</span></span>
            </div>
          </div>

          {/* Quick Metrics & Actions */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 px-3.5 py-2 rounded-xl">
              <div className="text-center px-2">
                <div className="text-lg font-bold text-rose-400">{highSeverityCount}</div>
                <div className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">High Flags</div>
              </div>
              <div className="w-px h-6 bg-slate-800"></div>
              <div className="text-center px-2">
                <div className="text-lg font-bold text-amber-400">{lowSeverityCount}</div>
                <div className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">Low Flags</div>
              </div>
              <div className="w-px h-6 bg-slate-800"></div>
              <div className="text-center px-2">
                <div className="text-lg font-bold text-indigo-400">{currentApp.documents.length}</div>
                <div className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">Docs</div>
              </div>
            </div>

            <button
              onClick={() => setSimDrawerOpen(!simDrawerOpen)}
              className={`flex items-center gap-1.5 px-3.5 py-2.5 rounded-xl border text-xs font-semibold transition ${
                simDrawerOpen
                  ? "bg-indigo-600 text-white border-indigo-500 shadow-md shadow-indigo-600/30"
                  : "bg-slate-800/80 hover:bg-slate-800 text-indigo-300 border-indigo-500/30"
              }`}
            >
              <Layers className="w-4 h-4 text-indigo-300" />
              <span>Impact Sim {excludedDocIds.length > 0 && `(${excludedDocIds.length})`}</span>
            </button>

            <button
              onClick={() => setDecisionModalOpen(true)}
              className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white text-xs font-bold shadow-lg shadow-indigo-500/20 transition"
            >
              <Scale className="w-4 h-4" />
              <span>Record Decision</span>
            </button>
          </div>
        </div>
      </section>

      {/* Evidence Removal Impact Simulator Drawer (FR-16) */}
      {simDrawerOpen && (
        <section className="bg-gradient-to-r from-indigo-950/70 via-slate-900 to-slate-900 border-b border-indigo-500/30 p-4 px-4 sm:px-6 lg:px-8 animate-in slide-in-from-top duration-200">
          <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-400" />
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  FR-16 Evidence Removal Impact Simulator
                </h3>
                <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  Interactive Stress Testing
                </span>
              </div>
              <p className="text-xs text-slate-300">
                Temporarily exclude specific claims or documents to simulate whether regulatory thresholds remain satisfied.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-4 text-xs">
              <div className="bg-slate-950/80 px-3.5 py-2 rounded-lg border border-slate-800 flex items-center gap-3">
                <span className="text-slate-400">Effective Land Area:</span>
                <span className={`font-mono font-bold ${landRequirementMet ? "text-emerald-400" : "text-rose-400"}`}>
                  {effectiveLandArea.toFixed(2)} Acres
                </span>
                <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                  landRequirementMet ? "bg-emerald-500/20 text-emerald-300" : "bg-rose-500/20 text-rose-300"
                }`}>
                  {landRequirementMet ? "Norms Met (>= 2.0 Ac)" : "Deficiency Triggered (< 2.0 Ac)"}
                </span>
              </div>

              {excludedDocIds.length > 0 && (
                <button
                  onClick={() => setExcludedDocIds([])}
                  className="text-xs text-indigo-400 hover:text-indigo-300 underline font-medium"
                >
                  Reset all exclusions
                </button>
              )}
            </div>
          </div>
        </section>
      )}

      {/* Main 3-Column Review Workspace (FR-14.2, FR-14.3, FR-14.4) */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8 grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* LEFT COLUMN: Document Explorer (4 Cols) */}
        <section className="lg:col-span-4 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <FileText className="w-4 h-4 text-indigo-400" />
              Documents ({currentApp.documents.length})
            </h2>
            <div className="flex items-center gap-1 text-[11px]">
              <button
                onClick={() => setSeverityFilter("all")}
                className={`px-2 py-0.5 rounded font-medium ${
                  severityFilter === "all" ? "bg-slate-800 text-white" : "text-slate-400 hover:text-slate-200"
                }`}
              >
                All
              </button>
              <button
                onClick={() => setSeverityFilter("high")}
                className={`px-2 py-0.5 rounded font-medium ${
                  severityFilter === "high" ? "bg-rose-500/20 text-rose-300" : "text-slate-400 hover:text-slate-200"
                }`}
              >
                High ({highSeverityCount})
              </button>
            </div>
          </div>

          {/* Document List */}
          <div className="space-y-2.5">
            {currentApp.documents.map((doc) => {
              const isExcluded = excludedDocIds.includes(doc.doc_id);
              const isSelected = activeDoc.doc_id === doc.doc_id;
              const hasFlags = doc.finding_ids.length > 0;

              return (
                <div
                  key={doc.doc_id}
                  onClick={() => {
                    setActiveDocId(doc.doc_id);
                    if (doc.finding_ids.length > 0) {
                      setActiveFindingId(doc.finding_ids[0]);
                    }
                  }}
                  className={`p-3.5 rounded-xl border transition-all cursor-pointer relative ${
                    isExcluded
                      ? "opacity-50 bg-slate-900/30 border-slate-800 border-dashed"
                      : isSelected
                      ? "bg-slate-900 border-indigo-500/80 shadow-md shadow-indigo-500/10 ring-1 ring-indigo-500/40"
                      : "bg-slate-900/60 hover:bg-slate-900 border-slate-800 hover:border-slate-700"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-1 pr-6">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-sm text-slate-100">{doc.name}</span>
                        {doc.overall === "flagged" && (
                          <span className="px-1.5 py-0.5 rounded bg-rose-500/15 text-rose-400 border border-rose-500/30 text-[10px] font-bold uppercase">
                            Flagged
                          </span>
                        )}
                        {doc.overall === "manual_review_required" && (
                          <span className="px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/30 text-[10px] font-bold uppercase">
                            Review
                          </span>
                        )}
                        {doc.overall === "no_issues" && (
                          <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 text-[10px] font-bold uppercase">
                            Clean
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                        {doc.note}
                      </p>
                    </div>

                    {/* Exclude Toggle Button for Simulator */}
                    <button
                      title={isExcluded ? "Include in analysis" : "Exclude in simulator"}
                      onClick={(e) => toggleExcludeDoc(doc.doc_id, e)}
                      className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
                    >
                      {isExcluded ? <EyeOff className="w-4 h-4 text-amber-400" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>

                  {/* Document Footer: Findings count & Verification tag */}
                  <div className="mt-3 pt-2.5 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
                    <span className="font-mono text-slate-500">{doc.doc_type}</span>
                    <div className="flex items-center gap-2">
                      {doc.verification === "verified" && (
                        <span className="flex items-center gap-1 text-emerald-400 font-medium">
                          <CheckCircle2 className="w-3 h-3" /> Signed & Verified
                        </span>
                      )}
                      {doc.verification === "expired" && (
                        <span className="flex items-center gap-1 text-rose-400 font-medium">
                          <Clock className="w-3 h-3" /> Expired
                        </span>
                      )}
                      {hasFlags && (
                        <span className="px-2 py-0.5 rounded-full bg-slate-800 text-rose-300 font-semibold border border-slate-700">
                          {doc.finding_ids.length} finding{doc.finding_ids.length > 1 ? "s" : ""}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Clean Documents Collapsible Accordion (FR-14.4) */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/30 p-3">
            <button
              onClick={() => setCleanCollapsed(!cleanCollapsed)}
              className="w-full flex items-center justify-between text-xs font-semibold text-slate-400 hover:text-slate-200"
            >
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                <span>Clean Supporting Documents ({selectedCaseId === "clean" ? 3 : 8})</span>
              </div>
              {cleanCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
            {!cleanCollapsed && (
              <div className="mt-3 pt-3 border-t border-slate-800/80 space-y-2 text-xs text-slate-400">
                <div className="flex items-center justify-between py-1">
                  <span>Certificate of Accreditation (NBA Tier-1)</span>
                  <span className="text-emerald-400">NBA-VERIFIED</span>
                </div>
                <div className="flex items-center justify-between py-1">
                  <span>Structural Safety Certificate (Form-B)</span>
                  <span className="text-emerald-400">VALID</span>
                </div>
                <div className="flex items-center justify-between py-1">
                  <span>Occupancy Certificate (Town Planning)</span>
                  <span className="text-emerald-400">VALID</span>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* MIDDLE COLUMN: Document Visual Inspector & Extracted Fields (4 Cols) */}
        <section className="lg:col-span-4 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <Eye className="w-4 h-4 text-indigo-400" />
              Document Inspector
            </h2>
            <span className="text-xs font-mono text-slate-400">{activeDoc.doc_id}</span>
          </div>

          {/* Simulated Document Preview Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
            <div className="p-3 bg-slate-800/60 border-b border-slate-800 flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-200">{activeDoc.name}</span>
              <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 font-mono text-slate-400 border border-slate-700">
                Page 1 of 1
              </span>
            </div>

            {/* Document Surface Preview with Simulated Bounding Box Highlights */}
            <div className="p-4 bg-slate-950 font-serif text-slate-200 text-xs min-h-[220px] relative border-b border-slate-800 flex flex-col justify-between">
              {activeDoc.previewContent ? (
                <div className="space-y-3">
                  <div className="text-center font-sans text-[11px] font-bold text-slate-400 border-b border-slate-800 pb-2">
                    {activeDoc.previewContent.header}
                  </div>
                  <div className="space-y-2 font-mono text-[11px]">
                    {activeDoc.previewContent.sections.map((sec, idx) => (
                      <div
                        key={idx}
                        className={`p-2 rounded transition ${
                          sec.highlight
                            ? "bg-rose-500/10 border border-rose-500/40 text-rose-200 font-bold"
                            : "bg-slate-900/60 text-slate-300 border border-slate-800/80"
                        }`}
                      >
                        <div className="text-[9px] uppercase tracking-wider text-slate-400 font-sans">{sec.label}</div>
                        <div>{sec.text}</div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-center h-32 text-slate-500 italic">
                  Document scanned preview rendered
                </div>
              )}

              {/* Stamp / Verification Ribbon */}
              {activeDoc.previewContent?.stamp && (
                <div className="mt-4 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] font-mono text-indigo-400">
                  <div className="flex items-center gap-1.5">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                    <span>{activeDoc.previewContent.stamp}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Extracted Fields Table */}
            <div className="p-4 bg-slate-900/50 space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Normalized Extracted Fields
              </h4>
              <div className="space-y-1.5">
                {Object.entries(activeDoc.fields).map(([key, item]) => (
                  <div
                    key={key}
                    className="p-2 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between text-xs"
                  >
                    <div>
                      <div className="font-mono text-slate-400 text-[11px]">{key}</div>
                      <div className="font-bold text-slate-100">
                        {String(item.value)} {item.unit || ""}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-[10px] text-slate-400">Confidence</div>
                      <div className={`font-mono font-bold ${item.confidence < 0.7 ? "text-amber-400" : "text-emerald-400"}`}>
                        {(item.confidence * 100).toFixed(0)}%
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* RIGHT COLUMN: Evidence Graph & Finding Deep Dive (4 Cols) */}
        <section className="lg:col-span-4 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              Evidence & Findings
            </h2>
            <span className="text-xs text-slate-400">
              {displayedFindings.length} active flag{displayedFindings.length === 1 ? "" : "s"}
            </span>
          </div>

          {activeFinding ? (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-4 shadow-lg">
              {/* Finding Header */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded border ${
                    activeFinding.severity === "high"
                      ? "bg-rose-500/20 text-rose-300 border-rose-500/40"
                      : "bg-amber-500/20 text-amber-300 border-amber-500/40"
                  }`}>
                    {activeFinding.severity} severity
                  </span>
                  <span className="text-xs font-mono text-indigo-400 font-bold">
                    {activeFinding.rule_id}
                  </span>
                </div>
                <h3 className="text-sm font-bold text-white leading-snug">
                  {activeFinding.message}
                </h3>
              </div>

              {/* Side-by-Side Conflicting Claims (FR-14.3) */}
              {activeFinding.claims.length > 0 && (
                <div className="space-y-2 pt-2 border-t border-slate-800">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                    <Scale className="w-3.5 h-3.5 text-indigo-400" />
                    Conflicting Claims Comparison
                  </h4>
                  <div className="space-y-2">
                    {activeFinding.claims.map((claim, idx) => (
                      <div
                        key={idx}
                        className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs space-y-1.5"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-slate-200">{claim.doc_name}</span>
                          <span className={`text-[9px] uppercase font-bold px-1.5 py-0.5 rounded ${
                            claim.authority === "issuer_verified"
                              ? "bg-emerald-500/20 text-emerald-300"
                              : claim.authority === "third_party"
                              ? "bg-indigo-500/20 text-indigo-300"
                              : "bg-slate-800 text-slate-400"
                          }`}>
                            {claim.authority.replace("_", " ")}
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-slate-300 font-mono">
                          <span>Claimed Value:</span>
                          <strong className="text-rose-400">{String(claim.value)}</strong>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Rule & Handbook Explanation */}
              {activeFinding.evidence.rule_desc && (
                <div className="p-3 rounded-lg bg-indigo-950/30 border border-indigo-500/20 text-xs text-indigo-200 leading-relaxed">
                  <strong className="block text-indigo-300 font-semibold mb-1">AICTE Regulatory Norm:</strong>
                  {activeFinding.evidence.rule_desc}
                </div>
              )}

              {/* Officer Action Panel (FR-15) */}
              <div className="pt-3 border-t border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                    FR-15 Officer Action
                  </h4>
                  {flagActions[activeFinding.finding_id] && (
                    <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300">
                      Action Recorded: {flagActions[activeFinding.finding_id].status}
                    </span>
                  )}
                </div>

                <textarea
                  value={actionInputReason}
                  onChange={(e) => setActionInputReason(e.target.value)}
                  placeholder="Enter mandatory rationale (e.g., 'Discrepancy verified against deed Schedule A...')"
                  rows={2}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleRecordFlagAction("confirmed")}
                    className="flex-1 py-2 px-3 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold transition shadow-sm"
                  >
                    Confirm Flag
                  </button>
                  <button
                    onClick={() => handleRecordFlagAction("dismissed")}
                    className="flex-1 py-2 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs font-bold transition"
                  >
                    Dismiss Flag
                  </button>
                </div>
              </div>

              {/* Other Findings for this Document */}
              <div className="pt-2 border-t border-slate-800 space-y-1.5">
                <span className="text-[11px] font-semibold text-slate-400">All Flags in this Application:</span>
                <div className="space-y-1">
                  {currentApp.findings.map(f => (
                    <button
                      key={f.finding_id}
                      onClick={() => setActiveFindingId(f.finding_id)}
                      className={`w-full text-left p-2 rounded text-xs transition flex items-center justify-between ${
                        activeFindingId === f.finding_id
                          ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/40 font-semibold"
                          : "hover:bg-slate-800/80 text-slate-400"
                      }`}
                    >
                      <span className="truncate">{f.message}</span>
                      <ChevronRight className="w-3.5 h-3.5 shrink-0 ml-1" />
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center text-slate-400 space-y-3">
              <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto" />
              <h3 className="text-sm font-bold text-white">No Issues Detected</h3>
              <p className="text-xs text-slate-400">
                All claims across documents agree with institutional records and Approval Process Handbook rules.
              </p>
            </div>
          )}
        </section>
      </main>

      {/* Decision Modal (FR-17) */}
      {decisionModalOpen && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 space-y-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Scale className="w-5 h-5 text-indigo-400" />
                <h3 className="font-bold text-base text-white">FR-17 Officer Final Scrutiny Decision</h3>
              </div>
              <button
                onClick={() => setDecisionModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              In accordance with AICTE policy, the decision-support engine presents findings and evidence, but the human officer retains full statutory authority.
            </p>

            <div className="space-y-2">
              <button
                onClick={() => {
                  setDecisionMade("Approved with Deficiencies");
                  setDecisionModalOpen(false);
                }}
                className="w-full p-3 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-left transition"
              >
                <div className="font-bold text-sm text-amber-300">Approve with Deficiencies</div>
                <div className="text-xs text-slate-400">Issue conditional EoA listing land and NOC deficiencies for 90-day rectification.</div>
              </button>

              <button
                onClick={() => {
                  setDecisionMade("Sent for Site Inspection");
                  setDecisionModalOpen(false);
                }}
                className="w-full p-3 rounded-xl bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 text-left transition"
              >
                <div className="font-bold text-sm text-indigo-300">Send for Site Inspection (Expert Visit Committee)</div>
                <div className="text-xs text-slate-400">Dispatch inspection team to measure physical campus parcel 45/2.</div>
              </button>

              <button
                onClick={() => {
                  setDecisionMade("Request Rectification");
                  setDecisionModalOpen(false);
                }}
                className="w-full p-3 rounded-xl bg-slate-800/80 hover:bg-slate-800 border border-slate-700 text-left transition"
              >
                <div className="font-bold text-sm text-slate-200">Request Rectification</div>
                <div className="text-xs text-slate-400">Return application to institution with deficiency checklist for re-upload.</div>
              </button>
            </div>

            <div className="pt-2 border-t border-slate-800 flex justify-end">
              <button
                onClick={() => setDecisionModalOpen(false)}
                className="px-4 py-2 rounded-lg bg-slate-800 text-xs font-semibold text-slate-300 hover:text-white"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Cryptographic Audit Ledger Modal (FR-20) */}
      {ledgerModalOpen && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Database className="w-5 h-5 text-indigo-400" />
                <h3 className="font-bold text-base text-white">FR-20 Tamper-Evident Audit Ledger & Besu Anchor</h3>
              </div>
              <button
                onClick={() => setLedgerModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-300">
              Every finding, check result, and officer action is appended to an immutable SHA-256 hash chain anchored onto Hyperledger Besu.
            </p>

            <div className="space-y-2 font-mono text-xs max-h-64 overflow-y-auto pr-1">
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                <div className="flex items-center justify-between text-indigo-400">
                  <span>Seq #004 • finding_created</span>
                  <span className="text-slate-500">2027-01-20T14:22:31Z</span>
                </div>
                <div className="text-slate-300 text-[11px]">Payload: Finding LAND_AREA_AGREE (45/2 area mismatch 2.5 vs 2.1)</div>
                <div className="text-[10px] text-slate-500 break-all">Hash: 8f9b31d2e4c87102a0b94c36e890f5a2...</div>
              </div>

              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                <div className="flex items-center justify-between text-indigo-400">
                  <span>Seq #005 • flag_action</span>
                  <span className="text-slate-500">2027-01-20T14:25:10Z</span>
                </div>
                <div className="text-slate-300 text-[11px]">Action: Officer S. Mayee confirmed finding f_4a9c0181</div>
                <div className="text-[10px] text-slate-500 break-all">Hash: 11a4cf9834b2201980ffae5784910321...</div>
              </div>

              <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-500/30 space-y-1 text-emerald-300">
                <div className="flex items-center justify-between font-bold">
                  <span>Hyperledger Besu On-Chain Anchor</span>
                  <span className="text-emerald-400">TX CONFIRMED</span>
                </div>
                <div className="text-[11px]">Contract: AuditAnchor.sol @ 0x892a0b124890c375...</div>
                <div className="text-[10px] break-all">Tx Hash: 0x7c49b8091faec89920194857bca190471...</div>
              </div>
            </div>

            <div className="pt-2 border-t border-slate-800 flex justify-end">
              <button
                onClick={() => setLedgerModalOpen(false)}
                className="px-4 py-2 rounded-lg bg-slate-800 text-xs font-semibold text-slate-300 hover:text-white"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950 py-4 px-4 sm:px-6 lg:px-8 text-center text-xs text-slate-500">
        AICTE DocVerf Decision-Support Layer • Built for Smart India Hackathon Prototype • Strict Decision Support: The system never approves or rejects; an officer decides.
      </footer>
    </div>
  );
}
