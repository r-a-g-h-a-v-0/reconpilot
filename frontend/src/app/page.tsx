"use client";
import { useState, useEffect } from "react";

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

export default function Dashboard() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [cash, setCash] = useState<CashPosition | null>(null);
  const [matches, setMatches] = useState<FullCase[]>([]);
  const [exceptions, setExceptions] = useState<FullCase[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  // File states
  const [bankFile, setBankFile] = useState<File | null>(null);
  const [invFile, setInvFile] = useState<File | null>(null);
  const [glFile, setGlFile] = useState<File | null>(null);

  const fetchDashboard = async () => {
    try {
      const [mRes, cRes, matchRes, excRes, auditRes] = await Promise.all([
        fetch("http://localhost:8000/api/metrics"),
        fetch("http://localhost:8000/api/cash_position"),
        fetch("http://localhost:8000/api/matches"),
        fetch("http://localhost:8000/api/exceptions"),
        fetch("http://localhost:8000/api/audit-events")
      ]);

      if (mRes.ok) setMetrics(await mRes.json());
      if (cRes.ok) setCash(await cRes.json());
      if (matchRes.ok) setMatches(await matchRes.json());
      if (excRes.ok) setExceptions(await excRes.json());
      if (auditRes.ok) setAuditEvents(await auditRes.json());
    } catch (e) {
      console.error(e);
      // Fail silently for initial load if backend is empty/not ready
    }
  };

  useEffect(() => {
    // eslint-disable-next-line
    fetchDashboard();
  }, []);

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
      const upRes = await fetch("http://localhost:8000/api/upload", { method: "POST", body: fd });
      if (!upRes.ok) throw new Error("Upload failed.");
      const recRes = await fetch("http://localhost:8000/api/reconcile", { method: "POST" });
      if (!recRes.ok) throw new Error("Reconciliation failed.");
      
      await fetchDashboard();
    } catch (e: unknown) {
      console.error(e);
      if (e instanceof Error) setErrorMsg(e.message || "An error occurred during upload/reconciliation.");
    }
    setLoading(false);
  };

  const handleReview = async (caseId: string, action: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/review`, { 
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ case_id: caseId, action: action, reason: "Manual review from dashboard" })
      });
      if (!res.ok) throw new Error("Review action failed");
      await fetchDashboard();
    } catch (e: unknown) {
      console.error(e);
      if (e instanceof Error) alert(e.message);
    }
  };

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(val);
  };

  return (
    <div className="min-h-screen bg-slate-50 p-8 text-slate-800">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <header className="flex justify-between items-center bg-white p-6 rounded-xl shadow-sm border border-slate-100">
          <div>
            <h1 className="text-3xl font-bold text-navy">ReconPilot Dashboard</h1>
            <p className="text-slate-500">AI Finance Controller for Indian SMBs</p>
          </div>
          <div className="bg-saffron-light text-saffron px-4 py-2 rounded-full font-semibold text-sm border border-saffron">
            Gemini AI Active
          </div>
        </header>

        {/* Upload & Reconciliation Controls */}
        <section className="bg-white p-6 rounded-xl shadow-sm border border-slate-100">
          <h2 className="text-lg font-bold text-navy mb-4">Run Reconciliation</h2>
          {errorMsg && <div className="mb-4 text-sm text-red-600 bg-red-50 p-3 rounded">{errorMsg}</div>}
          <div className="flex flex-col md:flex-row gap-4 items-end">
            <div className="flex-1 w-full">
              <label className="block text-sm font-medium text-slate-700 mb-1">Bank CSV</label>
              <input type="file" onChange={e => setBankFile(e.target.files?.[0] || null)} className="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-navy file:text-white hover:file:bg-blue-900"/>
            </div>
            <div className="flex-1 w-full">
              <label className="block text-sm font-medium text-slate-700 mb-1">Invoices CSV</label>
              <input type="file" onChange={e => setInvFile(e.target.files?.[0] || null)} className="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-navy file:text-white hover:file:bg-blue-900"/>
            </div>
            <div className="flex-1 w-full">
              <label className="block text-sm font-medium text-slate-700 mb-1">GL CSV</label>
              <input type="file" onChange={e => setGlFile(e.target.files?.[0] || null)} className="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-navy file:text-white hover:file:bg-blue-900"/>
            </div>
            <button onClick={handleUpload} disabled={loading} className="w-full md:w-auto bg-saffron text-white px-6 py-2 rounded-md font-semibold hover:bg-orange-600 disabled:opacity-50 transition-colors shadow-sm">
              {loading ? "Processing..." : "Upload & Reconcile"}
            </button>
          </div>
          <p className="text-xs text-slate-400 mt-3">* Uploading data clears the previous run and runs a fresh reconciliation loop.</p>
        </section>

        {(!metrics || metrics.total_cases === 0) && !loading && (
          <div className="text-center py-20 text-slate-400 bg-white rounded-xl border border-slate-100 shadow-sm">
            <p className="text-lg">No reconciliation data available.</p>
            <p className="text-sm">Please upload the Bank, Invoice, and GL files to begin.</p>
          </div>
        )}

        {metrics && metrics.total_cases > 0 && cash && (
          <>
            {/* Cash Position & Metrics Grid */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-navy text-white p-6 rounded-xl shadow-sm md:col-span-1">
                <div className="text-sm opacity-80 mb-1">Current Cash Position</div>
                <div className="text-3xl font-bold">{formatCurrency(cash.current_balance)}</div>
                <div className="text-xs mt-2 text-green-300">+{formatCurrency(cash.reconciled_credits)} Reconciled</div>
              </div>
              
              <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 md:col-span-3">
                <div className="text-sm font-bold text-navy mb-3">Operational Metrics</div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                  <div>
                    <div className="text-2xl font-bold text-slate-800">{metrics.total_cases}</div>
                    <div className="text-xs text-slate-500 uppercase">Total Cases</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-green-600">{metrics.automatic_matches}</div>
                    <div className="text-xs text-slate-500 uppercase">Auto Matches</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-saffron">{metrics.review_cases}</div>
                    <div className="text-xs text-slate-500 uppercase">Review Cases</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-red-500">{metrics.unresolved_exceptions}</div>
                    <div className="text-xs text-slate-500 uppercase">Exceptions</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Exceptions / Human Review */}
            <section className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
              <div className="bg-slate-50 p-4 border-b border-slate-100 flex justify-between items-center">
                <h2 className="text-lg font-bold text-navy">Exceptions & Human Review</h2>
                <span className="bg-saffron text-white text-xs px-2 py-1 rounded-full font-bold">{exceptions.length}</span>
              </div>
              
              {exceptions.length === 0 ? (
                <div className="p-8 text-center text-slate-500">No unresolved exceptions or reviews pending.</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-slate-50 text-slate-600">
                      <tr>
                        <th className="py-3 px-4 font-semibold">Case / Bank TXN</th>
                        <th className="py-3 px-4 font-semibold">Matched Invoice</th>
                        <th className="py-3 px-4 font-semibold">Reasoning</th>
                        <th className="py-3 px-4 font-semibold">Status</th>
                        <th className="py-3 px-4 font-semibold">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {exceptions.map((c) => {
                        const isAiAssisted = c.case.ai_provider != null;
                        const pendingReview = c.case.status === "needs_human_review";
                        
                        return (
                          <tr key={c.case.case_id} className="hover:bg-slate-50">
                            <td className="py-4 px-4 align-top">
                              <div className="font-mono text-xs text-slate-400">{c.case.case_id}</div>
                              <div className="font-semibold text-slate-800">{c.bank?.description}</div>
                              <div className="text-navy font-bold">{formatCurrency(c.bank?.amount || 0)}</div>
                              <div className="text-xs text-slate-500">{c.bank?.date}</div>
                            </td>
                            <td className="py-4 px-4 align-top">
                              {c.invoice ? (
                                <>
                                  <div className="font-semibold text-slate-800">{c.invoice.client_name}</div>
                                  <div className="font-mono text-xs text-slate-500">{c.invoice.invoice_id}</div>
                                  <div className="text-slate-600">{formatCurrency(c.invoice.total_amount)}</div>
                                </>
                              ) : c.case.ai_suggested_invoice ? (
                                <>
                                  <div className="font-mono text-xs text-saffron font-bold">{c.case.ai_suggested_invoice}</div>
                                  <div className="text-xs text-slate-500">(Suggested by AI)</div>
                                </>
                              ) : (
                                <span className="text-slate-400 italic">None</span>
                              )}
                            </td>
                            <td className="py-4 px-4 align-top max-w-md">
                              <div className="text-slate-700 mb-2"><strong>Engine:</strong> {c.case.reason}</div>
                              {isAiAssisted && (
                                <div className="bg-saffron-light/30 border border-saffron-light rounded p-2 mt-2">
                                  <div className="text-xs font-bold text-saffron mb-1 flex items-center gap-1">
                                    ✨ AI Suggestion — Pending accountant approval ({c.case.ai_provider})
                                  </div>
                                  <div className="text-xs text-slate-700">
                                    <strong>Recommendation:</strong> {c.case.ai_recommendation?.replace(/_/g, ' ')} <br/>
                                    <strong>Reason:</strong> {c.case.ai_reason}
                                  </div>
                                </div>
                              )}
                            </td>
                            <td className="py-4 px-4 align-top">
                              <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-bold ${
                                pendingReview ? 'bg-saffron text-white' : 'bg-red-100 text-red-700'
                              }`}>
                                {c.case.status.replace(/_/g, ' ').toUpperCase()}
                              </span>
                            </td>
                            <td className="py-4 px-4 align-top">
                              {pendingReview && (
                                <div className="flex gap-2">
                                  <button onClick={() => handleReview(c.case.case_id, "approve")} className="bg-green-600 hover:bg-green-700 text-white px-3 py-1.5 rounded text-xs font-bold transition-colors">Approve</button>
                                  <button onClick={() => handleReview(c.case.case_id, "reject")} className="bg-red-600 hover:bg-red-700 text-white px-3 py-1.5 rounded text-xs font-bold transition-colors">Reject</button>
                                </div>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {/* Matched Transactions */}
            <section className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
              <div className="bg-slate-50 p-4 border-b border-slate-100 flex justify-between items-center">
                <h2 className="text-lg font-bold text-navy">Matched Transactions</h2>
                <span className="bg-green-100 text-green-800 text-xs px-2 py-1 rounded-full font-bold">{matches.length}</span>
              </div>
              
              {matches.length === 0 ? (
                <div className="p-8 text-center text-slate-500">No matched transactions found.</div>
              ) : (
                <div className="overflow-x-auto max-h-96">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-slate-50 text-slate-600 sticky top-0 shadow-sm">
                      <tr>
                        <th className="py-3 px-4 font-semibold">Bank TXN</th>
                        <th className="py-3 px-4 font-semibold">Invoice</th>
                        <th className="py-3 px-4 font-semibold">Method</th>
                        <th className="py-3 px-4 font-semibold">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {matches.map((c) => {
                        const isManual = c.case.status === "matched_manual_review";
                        return (
                          <tr key={c.case.case_id} className="hover:bg-slate-50">
                            <td className="py-3 px-4">
                              <div className="font-semibold text-slate-800">{c.bank?.description}</div>
                              <div className="text-navy font-bold">{formatCurrency(c.bank?.amount || 0)}</div>
                            </td>
                            <td className="py-3 px-4">
                              <div className="font-semibold text-slate-800">{c.invoice?.client_name || c.case.invoice_id}</div>
                              <div className="text-slate-500">{formatCurrency(c.invoice?.total_amount || 0)}</div>
                            </td>
                            <td className="py-3 px-4 text-slate-600">
                              {c.case.match_method}
                            </td>
                            <td className="py-3 px-4">
                              <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-bold ${
                                isManual ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'
                              }`}>
                                {c.case.status.replace(/_/g, ' ').toUpperCase()}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {/* Audit Trail */}
            <section className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
              <div className="bg-slate-50 p-4 border-b border-slate-100 flex justify-between items-center">
                <h2 className="text-lg font-bold text-navy">Audit Trail</h2>
                <span className="bg-slate-200 text-slate-700 text-xs px-2 py-1 rounded-full font-bold">{auditEvents.length}</span>
              </div>
              
              {auditEvents.length === 0 ? (
                <div className="p-8 text-center text-slate-500">No audit events recorded.</div>
              ) : (
                <div className="overflow-x-auto max-h-96">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-slate-50 text-slate-600 sticky top-0 shadow-sm">
                      <tr>
                        <th className="py-3 px-4 font-semibold">Timestamp</th>
                        <th className="py-3 px-4 font-semibold">Case ID</th>
                        <th className="py-3 px-4 font-semibold">State Change</th>
                        <th className="py-3 px-4 font-semibold">Reviewer</th>
                        <th className="py-3 px-4 font-semibold">Reason</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {auditEvents.map((ev) => {
                        const isAI = ev.reviewer_name?.includes("AI");
                        return (
                          <tr key={ev.id} className="hover:bg-slate-50">
                            <td className="py-3 px-4 text-slate-500 text-xs whitespace-nowrap">
                              {new Date(ev.timestamp).toLocaleString()}
                            </td>
                            <td className="py-3 px-4 font-mono text-xs text-slate-600">{ev.case_id}</td>
                            <td className="py-3 px-4">
                              <div className="flex items-center gap-2 text-xs">
                                <span className="bg-slate-100 text-slate-500 px-1 rounded">{ev.previous_state}</span>
                                <span className="text-slate-400">→</span>
                                <span className="bg-slate-100 text-slate-800 px-1 rounded font-semibold">{ev.new_state}</span>
                              </div>
                            </td>
                            <td className="py-3 px-4">
                              <span className={`inline-flex px-2 py-0.5 rounded text-xs font-bold ${
                                isAI ? 'bg-saffron-light text-saffron' : 'bg-navy text-white'
                              }`}>
                                {ev.reviewer_name || "System"}
                              </span>
                            </td>
                            <td className="py-3 px-4 text-slate-700 max-w-md" title={ev.reason}>
                              {ev.reason}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

          </>
        )}
      </div>
    </div>
  );
}
