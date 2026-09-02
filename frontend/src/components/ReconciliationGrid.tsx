import React, { useState, useMemo } from 'react';

// --- Types ---
export type Candidate = {
  invoice_id: string;
  client_name: string;
  amount: number;
  date: string;
  similarity_score: number;
  rank: number;
};

export type CaseObj = {
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

export type FullCase = {
  case: CaseObj;
  bank: Bank;
  invoice: Invoice | null;
};

// --- Reusable Status Badge ---
export const StatusBadge = ({ status }: { status: string }) => {
  const getStyles = () => {
    switch (status) {
      case "matched_exact":
        return "bg-green-100 text-green-800 border-green-200";
      case "matched_timing":
      case "matched_fuzzy":
        return "bg-green-50 text-green-700 border-green-200";
      case "matched_manual_review":
        return "bg-blue-100 text-blue-800 border-blue-200";
      case "needs_human_review":
        return "bg-orange-100 text-orange-800 border-orange-200";
      case "duplicate_payment":
        return "bg-purple-100 text-purple-800 border-purple-200";
      case "missing_invoice":
      case "missing_gl_entry":
      case "unmatched":
        return "bg-red-100 text-red-800 border-red-200";
      case "amount_mismatch_tds":
      case "amount_mismatch_bank_fee":
        return "bg-yellow-100 text-yellow-800 border-yellow-200";
      default:
        return "bg-slate-100 text-slate-800 border-slate-200";
    }
  };

  const getLabel = () => {
    return status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold border ${getStyles()}`}>
      {getLabel()}
    </span>
  );
};

// --- Icons ---
const IconSearch = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>;
const IconChevronUp = () => <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="18 15 12 9 6 15"/></svg>;
const IconChevronDown = () => <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>;
const IconSparkle = () => <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3z"/></svg>;

// --- Main Grid Component ---
export default function ReconciliationGrid({ data, onRowClick }: { data: FullCase[], onRowClick?: (c: FullCase) => void }) {
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [sortConfig, setSortConfig] = useState<{ key: string, direction: 'asc' | 'desc' }>({ key: 'date', direction: 'desc' });
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  // Parse Date helper for sorting DD-MM-YYYY
  const parseDate = (dStr: string) => {
    if (!dStr) return 0;
    const parts = dStr.split('-');
    if (parts.length === 3) {
      return new Date(`${parts[2]}-${parts[1]}-${parts[0]}`).getTime();
    }
    return 0;
  };

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(val);
  };

  // 1. Filter
  const filteredData = useMemo(() => {
    return data.filter(item => {
      // Search
      const searchStr = searchTerm.toLowerCase();
      const matchesSearch = !searchTerm || (
        item.bank.description.toLowerCase().includes(searchStr) ||
        item.bank.bank_txn_id.toLowerCase().includes(searchStr) ||
        (item.invoice?.client_name || "").toLowerCase().includes(searchStr) ||
        (item.invoice?.invoice_id || item.case.invoice_id || "").toLowerCase().includes(searchStr) ||
        item.case.case_id.toLowerCase().includes(searchStr)
      );

      // Status
      let matchesStatus = true;
      if (statusFilter !== "ALL") {
        const s = item.case.status;
        if (statusFilter === "MATCHED") {
          matchesStatus = ["matched_exact", "matched_timing", "matched_fuzzy"].includes(s);
        } else if (statusFilter === "MANUAL_REVIEW") {
          matchesStatus = s === "matched_manual_review";
        } else if (statusFilter === "EXCEPTIONS") {
          matchesStatus = ["needs_human_review", "missing_invoice", "missing_gl_entry", "amount_mismatch_tds", "amount_mismatch_bank_fee", "unmatched"].includes(s);
        } else if (statusFilter === "DUPLICATES") {
          matchesStatus = s === "duplicate_payment";
        }
      }

      return matchesSearch && matchesStatus;
    });
  }, [data, searchTerm, statusFilter]);

  // 2. Sort
  const sortedData = useMemo(() => {
    const sortable = [...filteredData];
    sortable.sort((a, b) => {
      let aVal: string | number = 0;
      let bVal: string | number = 0;

      if (sortConfig.key === 'date') {
        aVal = parseDate(a.bank.date);
        bVal = parseDate(b.bank.date);
      } else if (sortConfig.key === 'amount') {
        aVal = a.bank.amount;
        bVal = b.bank.amount;
      } else if (sortConfig.key === 'status') {
        aVal = a.case.status;
        bVal = b.case.status;
      }

      if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
      return 0;
    });
    return sortable;
  }, [filteredData, sortConfig]);

  // 3. Paginate
  const totalPages = Math.ceil(sortedData.length / rowsPerPage);
  const paginatedData = useMemo(() => {
    const start = (currentPage - 1) * rowsPerPage;
    return sortedData.slice(start, start + rowsPerPage);
  }, [sortedData, currentPage, rowsPerPage]);

  const handleSort = (key: string) => {
    let direction: 'asc' | 'desc' = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  const renderSortIcon = (columnKey: string) => {
    if (sortConfig.key !== columnKey) return <span className="w-3 opacity-20"><IconChevronDown /></span>;
    return sortConfig.direction === 'asc' ? <span className="w-3 text-navy"><IconChevronUp /></span> : <span className="w-3 text-navy"><IconChevronDown /></span>;
  };

  // Reset page when filters change
  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCurrentPage(1);
  }, [searchTerm, statusFilter, rowsPerPage]);

  if (!data || data.length === 0) {
    return (
      <div className="bg-white p-12 rounded-xl shadow-sm border border-slate-200 text-center text-slate-500">
        <p className="text-sm">No reconciliation records found.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden flex flex-col">
      {/* Toolbar */}
      <div className="p-4 border-b border-slate-100 bg-slate-50 flex flex-col sm:flex-row justify-between items-center gap-4">
        <div className="relative w-full sm:w-64">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
            <IconSearch />
          </div>
          <input
            type="text"
            placeholder="Search records..."
            className="pl-9 pr-4 py-1.5 w-full border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-navy/20"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-3 w-full sm:w-auto">
          <span className="text-xs font-semibold text-slate-500 uppercase">View:</span>
          <select
            className="border border-slate-200 rounded-md text-sm py-1.5 px-3 focus:outline-none focus:ring-2 focus:ring-navy/20 text-slate-700 bg-white"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="ALL">All Records</option>
            <option value="MATCHED">Matched</option>
            <option value="MANUAL_REVIEW">Manual Review</option>
            <option value="EXCEPTIONS">Exceptions</option>
            <option value="DUPLICATES">Duplicates</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto min-h-[400px]">
        <table className="w-full text-left text-sm whitespace-nowrap">
          <thead className="bg-white text-slate-500 border-b border-slate-200 sticky top-0 z-10 text-xs uppercase tracking-wider">
            <tr>
              <th className="py-3 px-4 font-bold cursor-pointer hover:bg-slate-50 transition-colors" onClick={() => handleSort('status')}>
                <div className="flex items-center gap-1">Status {renderSortIcon('status')}</div>
              </th>
              <th className="py-3 px-4 font-bold">Bank Transaction</th>
              <th className="py-3 px-4 font-bold">Counterparty</th>
              <th className="py-3 px-4 font-bold cursor-pointer hover:bg-slate-50 transition-colors" onClick={() => handleSort('amount')}>
                <div className="flex items-center gap-1">Amount {renderSortIcon('amount')}</div>
              </th>
              <th className="py-3 px-4 font-bold cursor-pointer hover:bg-slate-50 transition-colors" onClick={() => handleSort('date')}>
                <div className="flex items-center gap-1">Date {renderSortIcon('date')}</div>
              </th>
              <th className="py-3 px-4 font-bold">Match Type</th>
              <th className="py-3 px-4 font-bold">Target</th>
              <th className="py-3 px-4 font-bold text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-slate-700">
            {paginatedData.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-8 text-center text-slate-400 text-sm">
                  No records match your filters.
                </td>
              </tr>
            ) : (
              paginatedData.map((c) => {
                const hasAI = !!c.case.ai_provider;
                return (
                  <tr key={c.case.case_id} onClick={() => { if (onRowClick) onRowClick(c); }} className={`hover:bg-slate-50 transition-colors group ${onRowClick ? 'cursor-pointer' : ''}`}>
                    <td className="py-3 px-4">
                      <StatusBadge status={c.case.status} />
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-900 truncate max-w-[200px]" title={c.bank.description}>{c.bank.description}</div>
                      <div className="text-xs text-slate-500 font-mono">{c.bank.bank_txn_id}</div>
                    </td>
                    <td className="py-3 px-4">
                      {c.invoice?.client_name ? (
                        <div className="font-medium text-slate-700 truncate max-w-[150px]" title={c.invoice.client_name}>{c.invoice.client_name}</div>
                      ) : (
                        <span className="text-slate-400">â€”</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-bold text-navy">{formatCurrency(c.bank.amount)}</div>
                    </td>
                    <td className="py-3 px-4 text-slate-500">
                      {c.bank.date}
                    </td>
                    <td className="py-3 px-4">
                      {c.case.match_method ? (
                        <span className="text-xs text-slate-600 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">{c.case.match_method}</span>
                      ) : (
                        <span className="text-slate-400">â€”</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      {c.invoice?.invoice_id || c.case.invoice_id ? (
                        <div className="font-mono text-xs text-slate-600">{c.invoice?.invoice_id || c.case.invoice_id}</div>
                      ) : (
                        <span className="text-slate-400">â€”</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-3">
                        {hasAI && (
                          <div className="flex items-center gap-1 text-xs font-bold text-saffron bg-orange-50 px-2 py-1 rounded border border-orange-100" title="AI Advisory Available">
                            <IconSparkle /> AI Advisory
                          </div>
                        )}
                        <button
                          onClick={(e) => { e.stopPropagation(); if (onRowClick) onRowClick(c); }}
                          className="text-xs font-semibold text-navy hover:text-blue-600 transition-colors bg-white border border-slate-200 shadow-sm px-3 py-1.5 rounded-md hover:bg-slate-50"
                        >
                          View Details
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="p-4 border-t border-slate-100 bg-white flex flex-col sm:flex-row justify-between items-center gap-4 text-sm text-slate-600">
        <div>
          Showing {sortedData.length === 0 ? 0 : (currentPage - 1) * rowsPerPage + 1} to {Math.min(currentPage * rowsPerPage, sortedData.length)} of {sortedData.length} entries
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span>Rows per page:</span>
            <select
              className="border border-slate-200 rounded text-sm py-1 px-2 focus:outline-none"
              value={rowsPerPage}
              onChange={(e) => setRowsPerPage(Number(e.target.value))}
            >
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
            </select>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="px-2 py-1 rounded border border-slate-200 disabled:opacity-50 hover:bg-slate-50"
            >
              Prev
            </button>
            <span className="px-3 py-1 font-medium text-navy">
              {currentPage} / {totalPages || 1}
            </span>
            <button
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages || totalPages === 0}
              className="px-2 py-1 rounded border border-slate-200 disabled:opacity-50 hover:bg-slate-50"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
