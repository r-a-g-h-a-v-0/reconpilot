"use client";
import { useState, useEffect } from "react";

export default function Dashboard() {
  const [metrics, setMetrics] = useState<any>(null);
  const [cash, setCash] = useState<any>(null);
  const [cases, setCases] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  // File states
  const [bankFile, setBankFile] = useState<File | null>(null);
  const [invFile, setInvFile] = useState<File | null>(null);
  const [glFile, setGlFile] = useState<File | null>(null);

  const fetchDashboard = async () => {
    try {
      const mRes = await fetch("http://localhost:8000/api/metrics");
      setMetrics(await mRes.json());
      const cRes = await fetch("http://localhost:8000/api/cash_position");
      setCash(await cRes.json());
      const casesRes = await fetch("http://localhost:8000/api/cases");
      setCases(await casesRes.json());
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, []);

  const handleUpload = async () => {
    if (!bankFile || !invFile || !glFile) return alert("Please select all 3 files");
    setLoading(true);
    const fd = new FormData();
    fd.append("bank_csv", bankFile);
    fd.append("invoice_csv", invFile);
    fd.append("gl_csv", glFile);
    
    try {
      await fetch("http://localhost:8000/api/upload", {
        method: "POST",
        body: fd
      });
      await fetchDashboard();
    } catch (e) {
      console.error(e);
      alert("Upload failed");
    }
    setLoading(false);
  };

  const handleReview = async (caseId: string, action: string) => {
    try {
      await fetch(`http://localhost:8000/api/review?case_id=${caseId}&action=${action}`, { method: "POST" });
      await fetchDashboard();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="min-h-screen p-8 max-w-7xl mx-auto space-y-8">
      <header className="flex justify-between items-center bg-white p-6 rounded-xl shadow-sm border border-slate-100">
        <div>
          <h1 className="text-3xl font-bold text-navy">ReconPilot Dashboard</h1>
          <p className="text-slate-500">AI Finance Controller for Indian SMBs</p>
        </div>
        <div className="bg-saffron-light text-saffron px-4 py-2 rounded-full font-semibold text-sm border border-saffron">
          Mock AI Mode
        </div>
      </header>

      <section className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 flex gap-4 items-end">
        <div className="flex-1">
          <label className="block text-sm font-medium mb-1">Bank CSV</label>
          <input type="file" onChange={e => setBankFile(e.target.files?.[0] || null)} className="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-navy file:text-white hover:file:bg-blue-900"/>
        </div>
        <div className="flex-1">
          <label className="block text-sm font-medium mb-1">Invoices CSV</label>
          <input type="file" onChange={e => setInvFile(e.target.files?.[0] || null)} className="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-navy file:text-white hover:file:bg-blue-900"/>
        </div>
        <div className="flex-1">
          <label className="block text-sm font-medium mb-1">GL CSV</label>
          <input type="file" onChange={e => setGlFile(e.target.files?.[0] || null)} className="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-navy file:text-white hover:file:bg-blue-900"/>
        </div>
        <button onClick={handleUpload} disabled={loading} className="bg-saffron text-white px-6 py-2 rounded-full font-semibold hover:bg-orange-600 disabled:opacity-50">
          {loading ? "Processing..." : "Run Reconciliation"}
        </button>
      </section>

      {metrics && cash && (
        <>
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-navy text-white p-6 rounded-xl shadow-sm">
              <div className="text-sm opacity-80 mb-1">Cash Position</div>
              <div className="text-3xl font-bold">₹{cash.current_balance.toLocaleString()}</div>
              <div className="text-xs mt-2 text-green-300">+{cash.reconciled_credits.toLocaleString()} Reconciled</div>
            </div>
            <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100">
              <div className="text-sm text-slate-500 mb-1">Match Accuracy</div>
              <div className="text-3xl font-bold text-navy">{(metrics.accuracy * 100).toFixed(1)}%</div>
            </div>
            <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100">
              <div className="text-sm text-slate-500 mb-1">Coverage</div>
              <div className="text-3xl font-bold text-navy">{(metrics.coverage * 100).toFixed(1)}%</div>
            </div>
            <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 flex justify-around items-center">
              <div>
                <div className="text-xs text-slate-500 mb-1">Exceptions</div>
                <div className="text-xl font-bold text-red-500">{(metrics.exception_rate * 100).toFixed(1)}%</div>
              </div>
              <div>
                <div className="text-xs text-slate-500 mb-1">Review Rate</div>
                <div className="text-xl font-bold text-saffron">{(metrics.review_rate * 100).toFixed(1)}%</div>
              </div>
            </div>
          </div>

          <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-navy mb-4">Reconciliation Cases ({metrics.total})</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-200">
                    <th className="py-3 px-2 font-semibold text-slate-600">ID</th>
                    <th className="py-3 px-2 font-semibold text-slate-600">Bank TXN</th>
                    <th className="py-3 px-2 font-semibold text-slate-600">Status</th>
                    <th className="py-3 px-2 font-semibold text-slate-600">Reason</th>
                    <th className="py-3 px-2 font-semibold text-slate-600">Confidence</th>
                    <th className="py-3 px-2 font-semibold text-slate-600">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.map((c: any) => (
                    <tr key={c.case.case_id} className="border-b border-slate-100 hover:bg-slate-50">
                      <td className="py-3 px-2 text-sm text-slate-500">{c.case.case_id}</td>
                      <td className="py-3 px-2 text-sm">{c.bank?.description} <br/><span className="text-xs font-bold text-navy">₹{c.bank?.amount}</span></td>
                      <td className="py-3 px-2">
                        <span className={`px-2 py-1 rounded text-xs font-semibold ${c.case.status.includes('matched') ? 'bg-green-100 text-green-700' : c.case.status === 'needs_human_review' ? 'bg-saffron-light text-saffron' : 'bg-red-100 text-red-700'}`}>
                          {c.case.status.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td className="py-3 px-2 text-sm max-w-xs">{c.case.reason}</td>
                      <td className="py-3 px-2 text-sm">{c.case.confidence ? (c.case.confidence * 100).toFixed(0) + "%" : "-"}</td>
                      <td className="py-3 px-2">
                        {c.case.status === "needs_human_review" && (
                          <div className="flex gap-2">
                            <button onClick={() => handleReview(c.case.case_id, "approve")} className="bg-green-500 hover:bg-green-600 text-white px-3 py-1 rounded text-xs font-bold">Approve</button>
                            <button onClick={() => handleReview(c.case.case_id, "reject")} className="bg-red-500 hover:bg-red-600 text-white px-3 py-1 rounded text-xs font-bold">Reject</button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
