import { useEffect, useState, useCallback } from "react";
import { api, setOrg, getOrg, formatMoney } from "./api";
import "./App.css";

const STATUS_STYLES = {
  suggested: { label: "Suggested", cls: "status-suggested" },
  needs_review: { label: "Needs review", cls: "status-review" },
  reconciled: { label: "Reconciled", cls: "status-reconciled" },
  ignored: { label: "Ignored", cls: "status-ignored" },
};

function StatusBadge({ status }) {
  const s = STATUS_STYLES[status] || { label: status, cls: "" };
  return <span className={`badge ${s.cls}`}>{s.label}</span>;
}

function LineStatusBadge({ status }) {
  const map = {
    open: { label: "Open", cls: "status-review" },
    partially_funded: { label: "Partially funded", cls: "status-suggested" },
    funded: { label: "Funded", cls: "status-reconciled" },
  };
  const s = map[status] || { label: status, cls: "" };
  return <span className={`badge ${s.cls}`}>{s.label}</span>;
}

function App() {
  const [organizations, setOrganizations] = useState([]);
  const [org, setOrgState] = useState(getOrg());
  const [transactions, setTransactions] = useState([]);
  const [lineItems, setLineItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [busyType, setBusyType] = useState(null);
  const [importSummary, setImportSummary] = useState(null);
  const [importing, setImporting] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [txns, lis] = await Promise.all([
        api.getTransactions(),
        api.getLineItems(),
      ]);
      setTransactions(txns);
      setLineItems(lis);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadOrganizations = useCallback(async () => {
    try {
      const orgs = await api.getOrganizations();
      setOrganizations(orgs);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    loadOrganizations();
  }, [loadOrganizations]);

  useEffect(() => {
    loadData();
  }, [loadData, org]);

  const handleOrgChange = (e) => {
    const slug = e.target.value;
    setOrg(slug);
    setOrgState(slug);
    setImportSummary(null);
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setImporting(true);
    setError("");
    setImportSummary(null);
    try {
      const summary = await api.importCsv(file);
      setImportSummary(summary);
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setImporting(false);
      e.target.value = "";
    }
  };

  const runAction = async (type, id) => {
    setBusyId(id);
    setBusyType(type);
    setError("");
    try {
      if (type === "approve") await api.approveMatch(id);
      else if (type === "reject") await api.rejectMatch(id);
      else if (type === "ignore") await api.ignoreTransaction(id);
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
      setBusyType(null);
    }
  };

  const suggestedMatch = (txn) =>
    (txn.matches || []).find((m) => m.status === "proposed");

  return (
    <div className="app">
      <header className="header">
        <h1>CapitalRecon</h1>
        <div className="org-switcher">
          <label htmlFor="org">Organization:</label>
          <select id="org" value={org} onChange={handleOrgChange}>
            {organizations.map((o) => (
              <option key={o.slug} value={o.slug}>
                {o.name}
              </option>
            ))}
          </select>
        </div>
      </header>

      {error && <div className="alert error">{error}</div>}

      <section className="card">
        <h2>Import Bank Statement</h2>
        <input
          type="file"
          accept=".csv"
          onChange={handleFileUpload}
          disabled={importing}
        />
        {importing && <span className="muted">Importing…</span>}
        {importSummary && (
          <div className="import-summary">
            <p>
              <strong>{importSummary.imported}</strong> imported ·{" "}
              <strong>{importSummary.duplicates}</strong> duplicates ·{" "}
              <strong>{importSummary.errors.length}</strong> errors
            </p>
            {importSummary.errors.length > 0 && (
              <ul className="errors">
                {importSummary.errors.map((e, i) => (
                  <li key={i}>
                    Line {e.line}: {e.message}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>

      <section className="card">
        <h2>Transactions</h2>
        {loading ? (
          <p className="muted">Loading…</p>
        ) : transactions.length === 0 ? (
          <p className="muted">No transactions yet. Import a CSV to get started.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Description</th>
                  <th className="num">Amount</th>
                  <th>Status</th>
                  <th>Suggested Investor</th>
                  <th>Reference</th>
                  <th>Match Reason</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((t) => {
                  const m = suggestedMatch(t);
                  const isBusy = busyId === t.id;
                  return (
                    <tr key={t.id}>
                      <td>{t.date}</td>
                      <td className="desc">{t.description}</td>
                      <td className="num">{formatMoney(t.amount)}</td>
                      <td><StatusBadge status={t.status} /></td>
                      <td>{m ? m.investor_entity : "—"}</td>
                      <td>{m ? m.line_item_reference : "—"}</td>
                      <td className="reason">
                        {m
                          ? m.reason
                          : t.status === "needs_review"
                          ? t.needs_review_reason
                          : "—"}
                      </td>
                      <td className="actions">
                        {t.status === "suggested" && m && (
                          <>
                            <button
                              onClick={() => runAction("approve", m.id)}
                              disabled={busyId !== null}
                            >
                              {busyId === m.id && busyType === "approve"
                                ? "…"
                                : "Approve"}
                            </button>
                            <button
                              className="secondary"
                              onClick={() => runAction("reject", m.id)}
                              disabled={busyId !== null}
                            >
                              Reject
                            </button>
                          </>
                        )}
                        {(t.status === "suggested" ||
                          t.status === "needs_review") && (
                          <button
                            className="ghost"
                            onClick={() => runAction("ignore", t.id)}
                            disabled={busyId !== null}
                          >
                            {isBusy && busyType === "ignore" ? "…" : "Ignore"}
                          </button>
                        )}
                        {t.status === "needs_review" &&
                          (t.matches || [])
                            .filter((mm) => mm.status === "proposed")
                            .map((mm) => (
                              <button
                                key={mm.id}
                                className="small"
                                onClick={() => runAction("approve", mm.id)}
                                disabled={busyId !== null}
                              >
                                Approve {mm.line_item_reference}
                              </button>
                            ))}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card">
        <h2>Capital Call Line Items</h2>
        {loading ? (
          <p className="muted">Loading…</p>
        ) : lineItems.length === 0 ? (
          <p className="muted">No line items.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Call</th>
                  <th>Investor</th>
                  <th>Reference</th>
                  <th className="num">Called</th>
                  <th className="num">Funded</th>
                  <th className="num">Remaining</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {lineItems.map((li) => (
                  <tr key={li.id}>
                    <td>#{li.call_number}</td>
                    <td>{li.investor_entity}</td>
                    <td>{li.reference}</td>
                    <td className="num">{formatMoney(li.amount_called)}</td>
                    <td className="num">{formatMoney(li.amount_funded)}</td>
                    <td className="num">{formatMoney(li.remaining)}</td>
                    <td><LineStatusBadge status={li.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

export default App;
