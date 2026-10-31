import { useEffect, useState } from "react";
import { api, IpCount, RuleCount, StatsSummary, TrendPoint } from "../api/client";
import { StatTile } from "../components/StatTile";
import { TrendChart } from "../components/TrendChart";
import { useLanguage } from "../i18n/LanguageContext";

function BarList({ rows, noDataLabel }: { rows: { label: string; count: number }[]; noDataLabel: string }) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  if (rows.length === 0) return <p className="muted">{noDataLabel}</p>;
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
  const { t } = useLanguage();
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
      .then(([s, tr, r, i]) => {
        setSummary(s);
        setTrend(tr);
        setTopRules(r);
        setTopIps(i);
      })
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <p>{t("dashboard.loadError", { error })}</p>;
  if (!summary) return <p>{t("common.loading")}</p>;

  return (
    <div>
      <h2>{t("dashboard.title")}</h2>
      <div className="stat-row">
        <StatTile label={t("dashboard.totalRequests")} value={summary.total_requests} />
        <StatTile label={t("dashboard.blocked")} value={summary.total_blocked} />
        <StatTile label={t("dashboard.detected")} value={summary.total_detected} />
        <StatTile label={t("dashboard.uniqueIps")} value={summary.unique_ips} />
      </div>

      <div className="card">
        <h3>{t("dashboard.attackTrend")}</h3>
        <TrendChart data={trend} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <div className="card">
          <h3>{t("dashboard.topRules")}</h3>
          <BarList
            noDataLabel={t("common.noData")}
            rows={topRules.map((r) => ({
              label: `${r.rule_id} ${r.message ?? ""}`.trim(),
              count: r.count,
            }))}
          />
        </div>
        <div className="card">
          <h3>{t("dashboard.topIps")}</h3>
          <BarList noDataLabel={t("common.noData")} rows={topIps.map((i) => ({ label: i.ip, count: i.count }))} />
        </div>
      </div>
    </div>
  );
}
