"use client";
import { useState, useEffect, useCallback } from "react";
import ReconciliationGrid from "../components/ReconciliationGrid";
import DetailPanel from "../components/DetailPanel";

// --- Icons (Inline SVGs to avoid dependencies) ---
const IconHome = () => <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>;
const IconList = () => <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>;
const IconAlert = () => <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>;
const IconHistory = () => <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/></svg>;
const IconMenu = () => <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="18" x2="20" y2="18"/></svg>;
const IconX = () => <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>;
const IconUpload = () => <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>;

// --- Types ---
type Metrics = {
  total_cases: number;
  automatic_decisions: number;
  automatic_matches: number;
  review_cases: number;
  unresolved_exceptions: number;
  coverage: number;
  review_rate: number;
  exception_rate: number;
};

type CashPosition = {
  opening_balance: number;
  reconciled_credits: number;
  reconciled_debits: number;
  current_balance: number;
};

export type Candidate = {
  invoice_id: string;
  client_name: string;
  amount: number;
  date: string;
  similarity_score: number;
  rank: number;
};

type CaseObj = {
  case_id: string;
  bank_txn_id: string;
  confidence: number | null;
  reason: string;
  status: string;
  match_method: string | null;
  invoice_id: string | null;
  ai_recommendation: string | null;
  ai_suggested_invoice: string | null;
  ai_provider: string | null;
  ai_reason: string | null;
  ai_confidence: number | null;
  candidates: Candidate[] | null;
};

type Bank = {
  bank_txn_id: string;
  description: string;
  amount: number;
  date: string;
};

type Invoice = {
  invoice_id: string;
  total_amount: number;
  client_name: string;
};

type FullCase = {
  case: CaseObj;
  bank: Bank;
  invoice: Invoice | null;
};

type AuditEvent = {
  id: number;
  previous_state: string;
  reason: string;
  timestamp: string;
  case_id: string;
  new_state: string;
  reviewer_name: string;
};

// --- Main Component ---
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState("overview");
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [selectedCase, setSelectedCase] = useState<FullCase | null>(null);

  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [cash, setCash] = useState<CashPosition | null>(null);
  const [matches, setMatches] = useState<FullCase[]>([]);
  const [exceptions, setExceptions] = useState<FullCase[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const [bankFile, setBankFile] = useState<File | null>(null);
  const [invFile, setInvFile] = useState<File | null>(null);
  const [glFile, setGlFile] = useState<File | null>(null);

  const fetchDashboard = useCallback(async () => {
    try {
      const [mRes, cRes, matchRes, excRes, auditRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/metrics`),
        fetch(`${API_BASE_URL}/api/cash_position`),
        fetch(`${API_BASE_URL}/api/matches`),
        fetch(`${API_BASE_URL}/api/exceptions`),
        fetch(`${API_BASE_URL}/api/audit-events`)
      ]);

      if (mRes.ok) setMetrics(await mRes.json());
      if (cRes.ok) setCash(await cRes.json());
      if (matchRes.ok) setMatches(await matchRes.json());
      if (excRes.ok) setExceptions(await excRes.json());
      if (auditRes.ok) setAuditEvents(await auditRes.json());
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchDashboard();
  }, [fetchDashboard]);

  const handleReview = async (caseId: string, action: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ case_id: caseId, action: action, reason: "Manual review from dashboard" })
      });
      if (!res.ok) throw new Error("Review action failed");
      await fetchDashboard();
      setSelectedCase(null);
    } catch (e: unknown) {
      console.error(e);
      if (e instanceof Error) console.error("Review action failed:", e.message);
    }
  };

  const handleUpload = async () => {
    if (!bankFile || !invFile || !glFile) {
      setErrorMsg("Please select all 3 files (Bank, Invoice, GL) before running reconciliation.");
      return;
    }
    setLoading(true);
    setErrorMsg("");
    const fd = new FormData();
    fd.append("bank_csv", bankFile);
    fd.append("invoice_csv", invFile);
    fd.append("gl_csv", glFile);

    try {
      const upRes = await fetch(`${API_BASE_URL}/api/upload`, { method: "POST", body: fd });
      if (!upRes.ok) {
        const errorData = await upRes.json().catch(() => ({}));
        throw new Error(errorData.detail || "Upload failed.");
      }
      const recRes = await fetch(`${API_BASE_URL}/api/reconcile`, { method: "POST" });
      if (!recRes.ok) throw new Error("Reconciliation failed.");

      await fetchDashboard();
      setActiveTab("overview");
    } catch (e: unknown) {
      console.error(e);
      if (e instanceof Error) setErrorMsg(e.message || "An error occurred during upload/reconciliation.");
    }
    setLoading(false);
  };

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(val);
  };

  // Determine AI Provider dynamically
  const aiProvider = exceptions.find(e => e.case.ai_provider)?.case.ai_provider
    || matches.find(m => m.case.ai_provider)?.case.ai_provider;
  const aiStatusText = aiProvider ? `AI Advisory Â· ${aiProvider.charAt(0).toUpperCase() + aiProvider.slice(1)}` : "AI Advisory Â· Inactive";

  const navItems = [
    { id: "overview", label: "Overview", icon: <IconHome /> },
    { id: "reconciliation", label: "Reconciliation", icon: <IconList /> },
    { id: "exceptions", label: "Exceptions", icon: <IconAlert />, badge: exceptions.length > 0 ? exceptions.length : null },
    { id: "audit", label: "Audit Trail", icon: <IconHistory />, badge: auditEvents.length > 0 ? auditEvents.length : null },
  ];

  return (
    <div className="flex h-screen bg-slate-50 text-slate-800 font-sans overflow-hidden">

      {/* Mobile Sidebar Overlay */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 bg-slate-900/50 z-20 md:hidden"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar Navigation */}
      <aside className={`fixed inset-y-0 left-0 w-64 bg-navy text-white flex flex-col transition-transform duration-200 z-30 md:static md:translate-x-0 ${isMobileMenuOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="p-6 flex items-center justify-between border-b border-slate-700/50">
          <div>
            <h1 className="text-xl font-bold tracking-tight">ReconPilot</h1>
            <p className="text-xs text-slate-400 font-medium">Finance Controller</p>
          </div>
          <button className="md:hidden text-slate-300 hover:text-white" onClick={() => setIsMobileMenuOpen(false)}>
            <IconX />
          </button>
        </div>

        <nav className="flex-1 py-6 px-3 space-y-1 overflow-y-auto">
          {navItems.map(item => (
            <button
              key={item.id}
              onClick={() => { setActiveTab(item.id); setIsMobileMenuOpen(false); }}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                activeTab === item.id
                  ? "bg-blue-900/50 text-white"
                  : "text-slate-300 hover:bg-slate-800 hover:text-white"
              }`}
            >
              <div className="flex items-center gap-3">
                <span className={activeTab === item.id ? "text-saffron" : "text-slate-400"}>{item.icon}</span>
                {item.label}
              </div>
              {item.badge !== null && item.badge !== undefined && (
                <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                  activeTab === item.id ? "bg-saffron text-navy" : "bg-slate-700 text-slate-300"
                }`}>
                  {item.badge}
                </span>
              )}
            </button>
          ))}
        </nav>

        <div className="p-4 border-t border-slate-700/50">
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800 text-xs font-semibold text-slate-300">
            <div className={`w-2 h-2 rounded-full ${aiProvider ? "bg-saffron" : "bg-slate-500"}`}></div>
            {aiStatusText}
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Mobile Header */}
        <header className="md:hidden bg-white border-b border-slate-200 p-4 flex items-center justify-between shrink-0">
          <h1 className="font-bold text-navy">ReconPilot</h1>
          <button onClick={() => setIsMobileMenuOpen(true)} className="text-slate-600">
            <IconMenu />
          </button>
        </header>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-4 md:p-8">
          <div className="max-w-6xl mx-auto space-y-8">

            <header className="hidden md:flex justify-between items-end pb-4 border-b border-slate-200">
              <div>
                <h1 className="text-2xl font-bold text-navy capitalize">{activeTab.replace('_', ' ')}</h1>
                <p className="text-sm text-slate-500">Manage your reconciliation workflows and reviews.</p>
              </div>
            </header>

            {/* TAB: OVERVIEW */}
            {activeTab === "overview" && (
              <div className="space-y-6">

                {/* Metrics & Cash Position Grid */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                  {/* Cash Position */}
                  <div className="bg-navy text-white p-6 rounded-xl shadow-sm md:col-span-1 flex flex-col justify-between">
                    <div>
                      <div className="text-sm font-medium text-slate-400 mb-1">Current Cash Position</div>
                      <div className="text-3xl font-bold tracking-tight">
                        {cash ? formatCurrency(cash.current_balance) : "â€”"}
                      </div>
                    </div>
                    {cash && (
                      <div className="text-sm font-medium mt-4 text-green-400 flex items-center gap-1">
                        <span>+ {formatCurrency(cash.reconciled_credits)}</span>
                        <span className="text-slate-400 text-xs font-normal ml-1">Reconciled</span>
                      </div>
                    )}
                  </div>

                  {/* KPIs */}
                  <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 md:col-span-3">
                    <h2 className="text-sm font-bold text-navy mb-4 uppercase tracking-wider">Operational Metrics</h2>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                      <div>
                        <div className="text-3xl font-bold text-slate-800">{metrics?.total_cases ?? "â€”"}</div>
                        <div className="text-xs font-medium text-slate-500 mt-1">TOTAL CASES</div>
                      </div>
                      <div>
                        <div className="text-3xl font-bold text-green-600">{metrics?.automatic_matches ?? "â€”"}</div>
                        <div className="text-xs font-medium text-slate-500 mt-1">AUTO MATCHES</div>
                      </div>
                      <div>
                        <div className="text-3xl font-bold text-saffron">{metrics?.review_cases ?? "â€”"}</div>
                        <div className="text-xs font-medium text-slate-500 mt-1">REVIEW CASES</div>
                      </div>
                      <div>
                        <div className="text-3xl font-bold text-red-600">{metrics?.unresolved_exceptions ?? "â€”"}</div>
                        <div className="text-xs font-medium text-slate-500 mt-1">EXCEPTIONS</div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Upload Zone */}
                <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                  <div className="flex items-center gap-2 mb-4">
                    <span className="text-slate-500"><IconUpload /></span>
                    <h2 className="text-lg font-bold text-navy">Run Reconciliation</h2>
                  </div>
                  <p className="text-sm text-slate-500 mb-6">Upload your Bank, Invoice, and GL files to start a new reconciliation cycle.</p>

                  {errorMsg && <div className="mb-6 text-sm font-medium text-red-600 bg-red-50 border border-red-100 p-4 rounded-lg">{errorMsg}</div>}

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                    <div className="bg-slate-50 p-4 rounded-lg border border-slate-200 border-dashed hover:bg-slate-100 transition-colors">
                      <label className="block text-sm font-bold text-slate-700 mb-2">Bank Data</label>
                      <input type="file" onChange={e => setBankFile(e.target.files?.[0] || null)} className="block w-full text-xs text-slate-500 file:mr-4 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-navy file:text-white hover:file:bg-blue-900 cursor-pointer"/>
                    </div>
                    <div className="bg-slate-50 p-4 rounded-lg border border-slate-200 border-dashed hover:bg-slate-100 transition-colors">
                      <label className="block text-sm font-bold text-slate-700 mb-2">Invoice Data</label>
                      <input type="file" onChange={e => setInvFile(e.target.files?.[0] || null)} className="block w-full text-xs text-slate-500 file:mr-4 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-navy file:text-white hover:file:bg-blue-900 cursor-pointer"/>
                    </div>
                    <div className="bg-slate-50 p-4 rounded-lg border border-slate-200 border-dashed hover:bg-slate-100 transition-colors">
                      <label className="block text-sm font-bold text-slate-700 mb-2">GL Data</label>
                      <input type="file" onChange={e => setGlFile(e.target.files?.[0] || null)} className="block w-full text-xs text-slate-500 file:mr-4 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-navy file:text-white hover:file:bg-blue-900 cursor-pointer"/>
                    </div>
                  </div>

                  <div className="flex justify-end">
                    <button onClick={handleUpload} disabled={loading} className="bg-saffron text-white px-6 py-2.5 rounded-lg font-bold text-sm hover:bg-orange-600 disabled:opacity-50 transition-colors shadow-sm flex items-center gap-2">
                      {loading ? (
                        <>Processing...</>
                      ) : (
                        <>Start Reconciliation Process</>
                      )}
                    </button>
                  </div>
                </div>

                {/* Recent Activity */}
                {auditEvents.length > 0 && (
                  <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                    <div className="bg-slate-50 p-4 border-b border-slate-100">
                      <h2 className="text-lg font-bold text-navy">Recent Activity</h2>
                    </div>
                    <div className="divide-y divide-slate-100">
                      {auditEvents.slice(0, 5).map(ev => {
                        const isAI = ev.reviewer_name?.includes("AI");
                        const isSystem = ev.reviewer_name?.includes("System");
                        return (
                          <div key={ev.id} className="p-4 flex flex-col sm:flex-row sm:items-center justify-between hover:bg-slate-50 transition-colors gap-2">
                            <div>
                              <div className="flex items-center gap-2 mb-1">
                                <span className={`inline-flex px-2 py-0.5 rounded text-[10px] font-bold ${
                                  isAI ? 'bg-orange-100 text-orange-800 border border-orange-200' : (isSystem ? 'bg-slate-100 text-slate-600 border border-slate-200' : 'bg-navy text-white border border-navy')
                                }`}>
                                  {ev.reviewer_name || "System"}
                                </span>
                                <span className="text-xs text-slate-500 font-mono">{ev.case_id}</span>
                              </div>
                              <div className="text-xs text-slate-600">
                                Moved to <span className="font-semibold text-navy">{ev.new_state}</span>: <span className="text-slate-500 italic">{ev.reason}</span>
                              </div>
                            </div>
                            <div className="text-xs text-slate-400 shrink-0">
                              {new Date(ev.timestamp).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

              </div>
            )}

            {/* TAB: RECONCILIATION */}
            {activeTab === "reconciliation" && (
              <div className="space-y-4">
                <ReconciliationGrid data={[...matches, ...exceptions]} onRowClick={setSelectedCase} />
              </div>
            )}

            {/* TAB: EXCEPTIONS */}
            {activeTab === "exceptions" && (
              <div className="space-y-4">
                <ReconciliationGrid data={exceptions} onRowClick={setSelectedCase} />
              </div>
            )}

            {/* TAB: AUDIT TRAIL */}
            {activeTab === "audit" && (
              <div className="space-y-4">
                <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
                  <div className="bg-slate-50 p-4 border-b border-slate-100 flex justify-between items-center">
                    <h2 className="text-lg font-bold text-navy">Audit Trail</h2>
                    <span className="bg-slate-200 text-slate-700 text-xs px-2 py-1 rounded-full font-bold">{auditEvents.length}</span>
                  </div>

                  {auditEvents.length === 0 ? (
                    <div className="p-12 text-center text-slate-500 flex flex-col items-center">
                      <IconHistory />
                      <h3 className="mt-4 text-lg font-bold text-slate-700">No audit events recorded yet.</h3>
                      <p className="mt-2 text-sm">Activities will appear here once you run reconciliation or perform manual reviews.</p>
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-sm">
                        <thead className="bg-slate-50 text-slate-600 sticky top-0 shadow-sm border-b border-slate-200">
                          <tr>
                            <th className="py-3 px-4 font-semibold">Timestamp</th>
                            <th className="py-3 px-4 font-semibold">Reviewer</th>
                            <th className="py-3 px-4 font-semibold">Case Reference</th>
                            <th className="py-3 px-4 font-semibold">State Change</th>
                            <th className="py-3 px-4 font-semibold">Reason</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {auditEvents.map((ev) => {
                            const isAI = ev.reviewer_name?.includes("AI");
                            const isSystem = ev.reviewer_name?.includes("System");
                            return (
                              <tr key={ev.id} className="hover:bg-slate-50">
                                <td className="py-3 px-4 text-slate-500 text-xs whitespace-nowrap">
                                  {new Date(ev.timestamp).toLocaleString()}
                                </td>
                                <td className="py-3 px-4">
                                  <span className={`inline-flex px-2 py-0.5 rounded text-[10px] font-bold ${
                                    isAI ? 'bg-orange-100 text-orange-800 border border-orange-200' : (isSystem ? 'bg-slate-100 text-slate-600 border border-slate-200' : 'bg-navy text-white border border-navy')
                                  }`}>
                                    {ev.reviewer_name || "System"}
                                  </span>
                                </td>
                                <td className="py-3 px-4 font-mono text-xs text-slate-600">{ev.case_id}</td>
                                <td className="py-3 px-4">
                                  <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2 text-xs">
                                    <span className="bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded whitespace-nowrap">{ev.previous_state}</span>
                                    <span className="text-slate-400 hidden sm:inline">â†’</span>
                                    <span className="bg-blue-50 text-blue-800 px-1.5 py-0.5 rounded font-semibold whitespace-nowrap">{ev.new_state}</span>
                                  </div>
                                </td>
                                <td className="py-3 px-4 text-slate-700 min-w-[200px]" title={ev.reason}>
                                  {ev.reason}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            )}

          </div>
        </div>
      </main>

      <DetailPanel
        selectedCase={selectedCase}
        onClose={() => setSelectedCase(null)}
        onReview={handleReview}
        auditEvents={auditEvents}
      />
    </div>
  );
}
