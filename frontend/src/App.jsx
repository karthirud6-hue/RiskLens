import React, { useEffect, useRef, useState } from "react";

// Point this at wherever the FastAPI backend is running. Defaults to the
// local dev server started via `uvicorn app.main:app --reload`.
const API_BASE = "http://localhost:8000";

const MERCHANT_CATEGORIES = [
  "grocery", "electronics", "travel", "gambling", "crypto",
  "jewelry", "utilities", "food", "fashion", "money_transfer", "other",
];

const BAND_LABELS = {
  LOW: "Auto-approved",
  MEDIUM: "Flagged & monitored",
  HIGH: "Sent to manual review",
  CRITICAL: "Auto-blocked",
};

function Pill({ band }) {
  return <span className={`pill ${band}`}>{band}</span>;
}

function FactorBreakdown({ factors }) {
  if (!factors || factors.length === 0) {
    return <div className="action-text">No risk signals triggered — transaction looked clean.</div>;
  }
  return (
    <ul className="factor-list">
      {factors.map((f) => (
        <li key={f.code}>
          <div>
            <div>{f.label}</div>
            <div className="detail">{f.detail}</div>
          </div>
          <div className="factor-points">+{f.points}</div>
        </li>
      ))}
    </ul>
  );
}

function StatCard({ label, value, cls }) {
  return (
    <div className={`stat-card ${cls || ""}`}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
    </div>
  );
}

export default function App() {
  const [transactions, setTransactions] = useState([]);
  const [stats, setStats] = useState({ total: 0, by_band: { LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 }, avg_score: 0, fraud_catch_rate_pct: null });
  const [liveOn, setLiveOn] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const [loadingBurst, setLoadingBurst] = useState(false);
  const [customResult, setCustomResult] = useState(null);
  const [customLoading, setCustomLoading] = useState(false);
  const [showForm, setShowForm] = useState(true);
  const [apiError, setApiError] = useState(false);

  const [form, setForm] = useState({
    amount: 15000,
    user_avg_amount: 1200,
    merchant_category: "electronics",
    hour_of_day: 14,
    txn_count_last_hour: 1,
    geo_mismatch: false,
    new_device: false,
    implied_speed_kmh: 0,
    card_age_days: 400,
    failed_attempts_before_success: 0,
  });

  const intervalRef = useRef(null);

  async function refreshStats() {
    try {
      const res = await fetch(`${API_BASE}/api/stats`);
      const data = await res.json();
      setStats(data);
      setApiError(false);
    } catch (e) {
      setApiError(true);
    }
  }

  async function loadInitial() {
    try {
      const [txRes, statsRes] = await Promise.all([
        fetch(`${API_BASE}/api/transactions?limit=40`),
        fetch(`${API_BASE}/api/stats`),
      ]);
      const txData = await txRes.json();
      const statsData = await statsRes.json();
      setTransactions(txData.transactions || []);
      setStats(statsData);
      setApiError(false);
    } catch (e) {
      setApiError(true);
    }
  }

  useEffect(() => {
    loadInitial();
  }, []);

  useEffect(() => {
    if (liveOn) {
      intervalRef.current = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE}/api/simulate?count=1`, { method: "POST" });
          const data = await res.json();
          const [txn] = data.generated;
          setTransactions((prev) => [txn, ...prev].slice(0, 60));
          refreshStats();
          setApiError(false);
        } catch (e) {
          setApiError(true);
        }
      }, 1100);
    } else if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [liveOn]);

  async function handleBurst() {
    setLoadingBurst(true);
    try {
      const res = await fetch(`${API_BASE}/api/simulate?count=10`, { method: "POST" });
      const data = await res.json();
      setTransactions((prev) => [...data.generated, ...prev].slice(0, 60));
      refreshStats();
      setApiError(false);
    } catch (e) {
      setApiError(true);
    } finally {
      setLoadingBurst(false);
    }
  }

  async function handleCustomSubmit(e) {
    e.preventDefault();
    setCustomLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/score-custom`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      setCustomResult(data);
      setApiError(false);
    } catch (e) {
      setApiError(true);
    } finally {
      setCustomLoading(false);
    }
  }

  function updateForm(key, value) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  const bandCounts = stats.by_band || {};

  return (
    <div className="app">
      <header className="top">
        <div>
          <h1>
            RiskLens <span className="badge-track">AI Risk Manager</span>
          </h1>
          <div className="subtitle">
            Real-time transaction risk scoring &amp; simulated compliance automation — built for the Razorpay AI Builder Internship
          </div>
        </div>
      </header>

      {apiError && (
        <div className="panel" style={{ borderColor: "#e74c3c" }}>
          Can't reach the backend at <span className="mono">{API_BASE}</span>. Make sure{" "}
          <span className="mono">uvicorn app.main:app --reload</span> is running in <span className="mono">backend/</span>.
        </div>
      )}

      <div className="stats-row">
        <StatCard label="Total Scored" value={stats.total ?? 0} />
        <StatCard label="Auto-Approved" value={bandCounts.LOW ?? 0} cls="low" />
        <StatCard label="Flagged / Monitored" value={bandCounts.MEDIUM ?? 0} cls="medium" />
        <StatCard label="Manual Review" value={bandCounts.HIGH ?? 0} cls="high" />
        <StatCard label="Auto-Blocked" value={bandCounts.CRITICAL ?? 0} cls="critical" />
        <StatCard
          label="Injected-Fraud Catch Rate"
          value={stats.fraud_catch_rate_pct != null ? `${stats.fraud_catch_rate_pct}%` : "—"}
        />
      </div>

      <div className="controls">
        <button className={liveOn ? "live-on" : "primary"} onClick={() => setLiveOn((v) => !v)}>
          {liveOn ? "■ Stop Live Feed" : "▶ Start Live Feed"}
        </button>
        <button className="ghost" onClick={handleBurst} disabled={loadingBurst}>
          {loadingBurst ? "Generating…" : "Simulate Burst (10)"}
        </button>
        <button className="ghost" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Hide Custom Test" : "Test a Custom Transaction"}
        </button>
      </div>

      {showForm && (
        <div className="panel">
          <h2>Test a Custom Transaction (what-if scoring)</h2>
          <form className="custom-form" onSubmit={handleCustomSubmit}>
            <div className="field">
              <label>Amount (Rs.)</label>
              <input type="number" value={form.amount} min="1"
                onChange={(e) => updateForm("amount", parseFloat(e.target.value) || 0)} />
            </div>
            <div className="field">
              <label>User's Average Amount (Rs.)</label>
              <input type="number" value={form.user_avg_amount} min="1"
                onChange={(e) => updateForm("user_avg_amount", parseFloat(e.target.value) || 0)} />
            </div>
            <div className="field">
              <label>Merchant Category</label>
              <select value={form.merchant_category} onChange={(e) => updateForm("merchant_category", e.target.value)}>
                {MERCHANT_CATEGORIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Hour of Day (0-23)</label>
              <input type="number" value={form.hour_of_day} min="0" max="23"
                onChange={(e) => updateForm("hour_of_day", parseInt(e.target.value) || 0)} />
            </div>
            <div className="field">
              <label>Transactions in Last Hour</label>
              <input type="number" value={form.txn_count_last_hour} min="0"
                onChange={(e) => updateForm("txn_count_last_hour", parseInt(e.target.value) || 0)} />
            </div>
            <div className="field">
              <label>Implied Travel Speed (km/h)</label>
              <input type="number" value={form.implied_speed_kmh} min="0"
                onChange={(e) => updateForm("implied_speed_kmh", parseFloat(e.target.value) || 0)} />
            </div>
            <div className="field">
              <label>Card Age (days)</label>
              <input type="number" value={form.card_age_days} min="0"
                onChange={(e) => updateForm("card_age_days", parseInt(e.target.value) || 0)} />
            </div>
            <div className="field">
              <label>Failed Attempts Before This One</label>
              <input type="number" value={form.failed_attempts_before_success} min="0"
                onChange={(e) => updateForm("failed_attempts_before_success", parseInt(e.target.value) || 0)} />
            </div>
            <div className="field checkbox">
              <input type="checkbox" checked={form.geo_mismatch}
                onChange={(e) => updateForm("geo_mismatch", e.target.checked)} />
              <label>Geo mismatch (billing vs. transaction country)</label>
            </div>
            <div className="field checkbox">
              <input type="checkbox" checked={form.new_device}
                onChange={(e) => updateForm("new_device", e.target.checked)} />
              <label>New / unrecognized device</label>
            </div>
            <div className="field" style={{ justifyContent: "flex-end" }}>
              <button className="primary" type="submit" disabled={customLoading}>
                {customLoading ? "Scoring…" : "Score This Transaction"}
              </button>
            </div>
          </form>

          {customResult && (
            <div className="result-card">
              <div className="score-line">
                <div className="score-big">{customResult.score}</div>
                <Pill band={customResult.band} />
                <div className="action-text">{BAND_LABELS[customResult.band]} ({customResult.action})</div>
              </div>
              <FactorBreakdown factors={customResult.factors} />
            </div>
          )}
        </div>
      )}

      <div className="panel">
        <h2>Live Transaction Feed</h2>
        {transactions.length === 0 ? (
          <div className="empty-state">No transactions yet — hit "Start Live Feed" or "Simulate Burst" above.</div>
        ) : (
          <table className="feed">
            <thead>
              <tr>
                <th>Time</th>
                <th>User</th>
                <th>Amount</th>
                <th>Category</th>
                <th>Score</th>
                <th>Band</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((t) => (
                <React.Fragment key={t.id}>
                  <tr onClick={() => setExpandedId(expandedId === t.id ? null : t.id)}>
                    <td className="mono">{(t.timestamp || "").replace("T", " ")}</td>
                    <td className="mono">{t.user_id}</td>
                    <td>Rs.{Number(t.amount).toLocaleString()}</td>
                    <td>{t.merchant_category}</td>
                    <td><strong>{t.score}</strong></td>
                    <td><Pill band={t.band} /></td>
                    <td className="action-text">{BAND_LABELS[t.band]}</td>
                  </tr>
                  {expandedId === t.id && (
                    <tr className="expand-row">
                      <td colSpan={7}>
                        <FactorBreakdown factors={t.factors} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <footer className="note">
        Transactions here are synthetically generated (see backend/app/generator.py) since production payment data
        isn't available for a student build — scoring itself runs on engineered features only and never sees the
        injected ground-truth fraud label. "Injected-Fraud Catch Rate" measures how many injected fraud patterns
        were caught at HIGH or CRITICAL band, purely as a sanity check on the rule weights.
      </footer>
    </div>
  );
}
