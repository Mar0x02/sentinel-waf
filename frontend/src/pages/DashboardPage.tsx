import { useEffect, useState } from "react";
import { api, IpCount, RuleCount, StatsSummary, TrendPoint } from "../api/client";
import { StatTile } from "../components/StatTile";
import { TrendChart } from "../components/TrendChart";

function BarList({ rows }: { rows: { label: string; count: number }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  if (rows.length === 0) return <p className="muted">Tidak ada data.</p>;
  return (
    <div>
      {rows.map((row) => (
        <div className="bar-row" key={row.label}>
          <span title={row.label}>{row.label}</span>
          <div className="track">
            <div className="fill" style={{ width: `${(row.count / max) * 100}%` }} />
          </div>
          <span>{row.count}</span>
        </div>
      ))}
    </div>
  );
}

export function DashboardPage() {
  const [summary, setSummary] = useState<StatsSummary | null>(null);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [topRules, setTopRules] = useState<RuleCount[]>([]);
  const [topIps, setTopIps] = useState<IpCount[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.statsSummary(),
      api.statsTrend(),
      api.statsTopRules(8),
      api.statsTopIps(8),
    ])
      .then(([s, t, r, i]) => {
        setSummary(s);
        setTrend(t);
        setTopRules(r);
        setTopIps(i);
      })
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <p>Gagal memuat dashboard: {error}</p>;
  if (!summary) return <p>Loading...</p>;

  return (
    <div>
      <h2>Dashboard</h2>
      <div className="stat-row">
        <StatTile label="Total requests" value={summary.total_requests} />
        <StatTile label="Blocked" value={summary.total_blocked} />
        <StatTile label="Detected (not blocked)" value={summary.total_detected} />
        <StatTile label="Unique IPs" value={summary.unique_ips} />
      </div>

      <div className="card">
        <h3>Attack trend (per hour)</h3>
        <TrendChart data={trend} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <div className="card">
          <h3>Top triggered rules</h3>
          <BarList
            rows={topRules.map((r) => ({
              label: `${r.rule_id} ${r.message ?? ""}`.trim(),
              count: r.count,
            }))}
          />
        </div>
        <div className="card">
          <h3>Top offending IPs</h3>
          <BarList rows={topIps.map((i) => ({ label: i.ip, count: i.count }))} />
        </div>
      </div>
    </div>
  );
}
