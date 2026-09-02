import React from 'react';
import { FullCase, StatusBadge } from './ReconciliationGrid';

type AuditEvent = {
  id: number;
  previous_state: string;
  reason: string;
  timestamp: string;
  case_id: string;
  new_state: string;
  reviewer_name: string;
};

type DetailPanelProps = {
  selectedCase: FullCase | null;
  onClose: () => void;
  onReview: (caseId: string, action: string) => Promise<void>;
  auditEvents: AuditEvent[];
};

const IconX = () => <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>;
const IconSparkle = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3z"/></svg>;
const IconCheck = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>;

export default function DetailPanel({ selectedCase, onClose, onReview, auditEvents }: DetailPanelProps) {
  if (!selectedCase) return null;

  const { case: c, bank, invoice } = selectedCase;

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(val);
  };

  const caseAuditEvents = auditEvents.filter(e => e.case_id === c.case_id).sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

  const hasAI = !!c.ai_provider;
  // Determine if it needs review based on status
  const needsReview = c.status === "needs_human_review";

  return (
    <>
      <div className="fixed inset-0 bg-slate-900/40 z-40 transition-opacity" onClick={onClose} />

      <div className="fixed inset-y-0 right-0 w-full md:w-[60%] lg:w-[40%] bg-white shadow-2xl z-50 flex flex-col transform transition-transform duration-300 ease-in-out border-l border-slate-200">

        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-100 bg-slate-50">
          <div>
            <div className="text-xs font-mono text-slate-500 mb-2">{c.case_id}</div>
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-bold text-navy">{formatCurrency(bank.amount)}</h2>
              <StatusBadge status={c.status} />
            </div>
            <div className="text-sm text-slate-500 mt-1">{bank.date}</div>
          </div>
          <button onClick={onClose} className="p-2 text-slate-400 hover:bg-slate-200 hover:text-slate-700 rounded-full transition-colors">
            <IconX />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-8">

          {/* Bank Transaction */}
          <section>
            <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-4">Bank Transaction</h3>
            <div className="bg-white border border-slate-200 rounded-lg p-4 grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-slate-500 text-xs mb-1">Bank Txn ID</div>
                <div className="font-mono text-slate-800">{bank.bank_txn_id}</div>
              </div>
              <div>
                <div className="text-slate-500 text-xs mb-1">Date</div>
                <div className="text-slate-800">{bank.date}</div>
              </div>
              <div className="col-span-2">
                <div className="text-slate-500 text-xs mb-1">Description</div>
                <div className="text-slate-800 font-medium">{bank.description}</div>
              </div>
              <div>
                <div className="text-slate-500 text-xs mb-1">Amount</div>
                <div className="font-bold text-navy">{formatCurrency(bank.amount)}</div>
              </div>
            </div>
          </section>

          {/* System Evidence */}
          <section>
            <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-4">Reconciliation Evidence</h3>
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-slate-500 text-xs mb-1">Match Method</div>
                  <div className="text-slate-800 font-semibold">{c.match_method || "â€”"}</div>
                </div>
                <div>
                  <div className="text-slate-500 text-xs mb-1">System Confidence</div>
                  <div className="text-slate-800">{c.confidence ? `${(c.confidence * 100).toFixed(1)}%` : "â€”"}</div>
                </div>
              </div>
              <div>
                <div className="text-slate-500 text-xs mb-1">System Reason</div>
                <div className="text-slate-700">{c.reason || "â€”"}</div>
              </div>

            </div>
          </section>

          {/* Candidate Comparison */}
          {c.candidates && c.candidates.length > 0 && (
            <section>
              <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-4">Candidate Comparison</h3>
              {c.candidates.length > 1 && c.status === "needs_human_review" && (
                <div className="mb-4 p-3 bg-blue-50 border border-blue-100 rounded text-xs text-blue-800">
                  Multiple plausible candidates were found and the confidence margin was insufficient for automatic matching.
                </div>
              )}
              <div className="space-y-3">
                {c.candidates.map((cand) => (
                  <div key={cand.invoice_id} className={`border rounded-lg p-4 text-sm relative ${cand.rank === 1 ? 'border-navy bg-slate-50' : 'border-slate-200 bg-white'}`}>
                    {cand.rank === 1 && (
                      <div className="absolute top-0 right-0 bg-navy text-white text-[10px] font-bold px-2 py-0.5 rounded-bl-lg rounded-tr-lg">
                        TOP CANDIDATE
                      </div>
                    )}
                    <div className="flex justify-between mb-2">
                      <span className="font-bold text-slate-800">#{cand.rank} â€¢ {cand.client_name}</span>
                      <span className="text-navy font-bold">{formatCurrency(cand.amount)}</span>
                    </div>
                    <div className="flex justify-between text-slate-500 text-xs">
                      <span>Invoice ID: <span className="font-mono text-slate-700">{cand.invoice_id}</span> â€¢ Date: {cand.date}</span>
                      <span>Similarity: <span className="font-bold text-slate-700">{cand.similarity_score}%</span></span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Matched Record (if present) */}
          {invoice && (
            <section>
              <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-4">Target Invoice</h3>
              <div className="bg-white border border-slate-200 rounded-lg p-4 grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-slate-500 text-xs mb-1">Invoice ID</div>
                  <div className="font-mono text-slate-800">{invoice.invoice_id}</div>
                </div>
                <div>
                  <div className="text-slate-500 text-xs mb-1">Counterparty</div>
                  <div className="text-slate-800 font-medium">{invoice.client_name}</div>
                </div>
                <div>
                  <div className="text-slate-500 text-xs mb-1">Invoice Amount</div>
                  <div className="font-bold text-slate-800">{formatCurrency(invoice.total_amount)}</div>
                </div>
              </div>
            </section>
          )}

          {/* AI Advisory */}
          {hasAI && (
            <section>
              <div className="flex items-center gap-2 mb-4">
                <h3 className="text-sm font-bold text-saffron uppercase tracking-wider">AI Advisory</h3>
                <span className="bg-orange-100 text-orange-800 text-xs px-2 py-0.5 rounded font-bold border border-orange-200">
                  {c.ai_provider?.toUpperCase()}
                </span>
              </div>
              <div className="bg-gradient-to-br from-orange-50 to-white border border-orange-200 rounded-lg p-5 space-y-4">

                <div className="flex items-start gap-3">
                  <div className="text-saffron mt-0.5"><IconSparkle /></div>
                  <div>
                    <div className="text-xs font-bold text-orange-800 uppercase mb-1">Suggested Match</div>
                    <div className="font-mono text-sm text-slate-800 bg-white px-2 py-1 rounded border border-orange-100 inline-block shadow-sm">
                      {c.ai_suggested_invoice || "â€”"}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 pt-2">
                  <div>
                    <div className="text-slate-500 text-xs mb-1">AI Confidence</div>
                    <div className="text-slate-800 font-bold">{c.ai_confidence ? `${(c.ai_confidence * 100).toFixed(1)}%` : "â€”"}</div>
                  </div>
                  <div>
                    <div className="text-slate-500 text-xs mb-1">Recommendation</div>
                    <div className="text-slate-800 font-semibold capitalize">{c.ai_recommendation || "â€”"}</div>
                  </div>
                </div>

                <div className="pt-2">
                  <div className="text-slate-500 text-xs mb-1">AI Reasoning</div>
                  <div className="text-slate-700 text-sm leading-relaxed">{c.ai_reason || "â€”"}</div>
                </div>

                <div className="mt-4 flex items-center justify-center p-3 bg-orange-100/50 rounded-md border border-orange-200/50">
                  <p className="text-xs font-bold text-orange-900">AI suggestion â€” Pending accountant approval</p>
                </div>
              </div>
            </section>
          )}

          {/* Audit Timeline */}
          {caseAuditEvents.length > 0 && (
            <section>
              <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-4">Audit History</h3>
              <div className="space-y-4 relative before:absolute before:inset-0 before:ml-2 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-slate-200 before:to-transparent">
                {caseAuditEvents.map((ev) => (
                  <div key={ev.id} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
                    <div className="flex items-center justify-center w-5 h-5 rounded-full border-2 border-white bg-slate-300 group-[.is-active]:bg-navy text-slate-500 group-[.is-active]:text-white shadow shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2 z-10">
                      <div className="w-1.5 h-1.5 bg-white rounded-full"></div>
                    </div>
                    <div className="w-[calc(100%-2.5rem)] md:w-[calc(50%-1.5rem)] p-3 rounded-lg border border-slate-200 bg-white shadow-sm">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-bold text-slate-800 text-xs">{ev.reviewer_name || "System"}</span>
                        <span className="text-[10px] text-slate-400 font-mono">{new Date(ev.timestamp).toLocaleString()}</span>
                      </div>
                      <div className="text-xs text-slate-600 mb-2">
                        Moved from <span className="font-semibold">{ev.previous_state}</span> to <span className="font-semibold text-navy">{ev.new_state}</span>
                      </div>
                      <div className="text-xs text-slate-500 italic">&quot;{ev.reason}&quot;</div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

        </div>

        {/* Sticky Action Footer */}
        <div className="p-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between shrink-0">
          <div className="text-xs text-slate-500 font-medium">
            {needsReview ? "Final accountant decision required." : "Transaction is settled."}
          </div>
          <div className="flex items-center gap-3">
            {needsReview ? (
              <>
                <button
                  onClick={() => onReview(c.case_id, "reject")}
                  className="px-4 py-2 text-sm font-bold text-slate-600 hover:text-slate-900 hover:bg-slate-200 transition-colors rounded-lg border border-slate-300 bg-white shadow-sm"
                >
                  Reject
                </button>
                <button
                  onClick={() => onReview(c.case_id, "approve")}
                  className="flex items-center gap-2 px-6 py-2 text-sm font-bold text-white bg-navy hover:bg-blue-900 transition-colors rounded-lg shadow-md"
                >
                  <IconCheck /> Approve Match
                </button>
              </>
            ) : (
              <button
                onClick={onClose}
                className="px-6 py-2 text-sm font-bold text-slate-700 bg-white hover:bg-slate-100 transition-colors rounded-lg border border-slate-300 shadow-sm"
              >
                Close View
              </button>
            )}
          </div>
        </div>

      </div>
    </>
  );
}
