import { AlertTriangle } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, IpCount, RuleCount, RuleSet, StatsSummary, TrendPoint } from "../api/client";
import { LoadingInline } from "../components/LoadingShield";
import { RequestGlobe } from "../components/RequestGlobe";
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
          <span className="bar-label" title={row.label}>
            {row.label}
          </span>
          <div className="bar-track-row">
            <div className="track">
              <div className="fill" style={{ width: `${(row.count / max) * 100}%` }} />
            </div>
            <span className="bar-count">{row.count}</span>
          </div>
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
  const [ruleSets, setRuleSets] = useState<RuleSet[] | null>(null);

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
    api.listRuleSets().then(setRuleSets).catch(() => setRuleSets(null));
  }, []);

  if (error) return <p>{t("dashboard.loadError", { error })}</p>;
  if (!summary) return <LoadingInline />;

  // Base Tuning is always present and never counts as "configured" on its
  // own - a fresh install has zero active rules until something's
  // imported/enabled on the Rules page (see CLAUDE.md). This banner is
  // the UI-side nudge for that, gone the moment it's no longer true.
  const noActiveRules =
    ruleSets !== null && !ruleSets.some((rs) => rs.slug !== "base-tuning" && rs.enabled && rs.rule_count > 0);

  return (
    <div>
      {noActiveRules && (
        <div className="setup-banner">
          <AlertTriangle size={18} />
          <span>{t("dashboard.noRulesWarning")}</span>
          <Link to="/rules" className="btn btn-primary">
            {t("dashboard.noRulesAction")}
          </Link>
        </div>
      )}
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

      <RequestGlobe />

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
