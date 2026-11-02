import { AlertTriangle } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api, CategoryTrend, IpCount, RuleCount, RuleSet, StatsSummary, TrendPoint } from "../api/client";
import { CategoryTrendChart } from "../components/CategoryTrendChart";
import { DateRangePicker } from "../components/DateRangePicker";
import { LoadingInline } from "../components/LoadingShield";
import { Modal } from "../components/Modal";
import { RequestGlobe } from "../components/RequestGlobe";
import { StatTile } from "../components/StatTile";
import { TrendChart } from "../components/TrendChart";
import { useLanguage } from "../i18n/LanguageContext";

type ViewAllKind = "categories" | "rules" | "ips";

// Dashboard bar lists are always top-8/10 - this fetches the full ranked
// list (up to the API's own cap of 100) on demand instead of bloating the
// initial page load with data most views never need.
function ViewAllButton({ onClick, t }: { onClick: () => void; t: (key: string) => string }) {
  return (
    <button className="btn" onClick={onClick}>
      {t("dashboard.viewAll")}
    </button>
  );
}

function BarList({
  rows,
  noDataLabel,
}: {
  rows: { label: string; count: number; href?: string }[];
  noDataLabel: string;
}) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  if (rows.length === 0) return <p className="muted">{noDataLabel}</p>;
  return (
    <div>
      {rows.map((row) => {
        const content = (
          <>
            <span className="bar-label" title={row.label}>
              {row.label}
            </span>
            <div className="bar-track-row">
              <div className="track">
                <div className="fill" style={{ width: `${(row.count / max) * 100}%` }} />
              </div>
              <span className="bar-count">{row.count}</span>
            </div>
          </>
        );
        return row.href ? (
          <Link className="bar-row" key={row.label} to={row.href}>
            {content}
          </Link>
        ) : (
          <div className="bar-row" key={row.label}>
            {content}
          </div>
        );
      })}
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
  const [viewAll, setViewAll] = useState<ViewAllKind | null>(null);
  const [viewAllRows, setViewAllRows] = useState<{ label: string; count: number; href?: string }[] | null>(null);
  const [categoryDays, setCategoryDays] = useState(7);
  const [categoryTrend, setCategoryTrend] = useState<CategoryTrend | null>(null);

  useEffect(() => {
    Promise.all([api.statsSummary(), api.statsTrend(), api.statsTopRules(8), api.statsTopIps(8)])
      .then(([s, tr, r, i]) => {
        setSummary(s);
        setTrend(tr);
        setTopRules(r);
        setTopIps(i);
      })
      .catch((e) => setError(String(e)));
    api.listRuleSets().then(setRuleSets).catch(() => setRuleSets(null));
  }, []);

  useEffect(() => {
    // Keeps the previous chart on screen while a new range loads, rather
    // than clearing it - only the very first load has nothing to hold onto.
    api
      .statsCategoryTrend(categoryDays)
      .then(setCategoryTrend)
      .catch((e) => toast.error(String(e)));
  }, [categoryDays]);

  function openViewAll(kind: ViewAllKind) {
    setViewAll(kind);
    setViewAllRows(null);
    const fetchRows =
      kind === "categories"
        ? api
            .statsTopCategories(100)
            .then((rows) =>
              rows.map((c) => ({
                label: c.category,
                count: c.count,
                href: `/logs?category=${encodeURIComponent(c.category)}`,
              }))
            )
        : kind === "rules"
          ? api
              .statsTopRules(100)
              .then((rows) =>
                rows.map((r) => ({
                  label: `${r.rule_id} ${r.message ?? ""}`.trim(),
                  count: r.count,
                  href: `/logs?rule_id=${encodeURIComponent(r.rule_id)}`,
                }))
              )
          : api
              .statsTopIps(100)
              .then((rows) =>
                rows.map((i) => ({ label: i.ip, count: i.count, href: `/logs?client_ip=${encodeURIComponent(i.ip)}` }))
              );
    fetchRows.then(setViewAllRows).catch((e) => toast.error(String(e)));
  }

  const viewAllTitle =
    viewAll === "categories"
      ? t("dashboard.topCategories")
      : viewAll === "rules"
        ? t("dashboard.topRules")
        : t("dashboard.topIps");

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

      <div className="card">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <h3 style={{ marginRight: "auto" }}>{t("dashboard.topCategories")}</h3>
          <DateRangePicker
            value={categoryDays}
            onChange={setCategoryDays}
            options={[
              { days: 7, label: t("dashboard.last7Days") },
              { days: 14, label: t("dashboard.last14Days") },
              { days: 30, label: t("dashboard.last30Days") },
              { days: 90, label: t("dashboard.last90Days") },
            ]}
          />
          <ViewAllButton t={t} onClick={() => openViewAll("categories")} />
        </div>
        <p className="muted">{t("dashboard.topCategoriesHint")}</p>
        {categoryTrend === null ? <LoadingInline /> : <CategoryTrendChart data={categoryTrend} />}
      </div>

      <RequestGlobe />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <div className="card">
          <div style={{ display: "flex", alignItems: "center" }}>
            <h3 style={{ marginRight: "auto" }}>{t("dashboard.topRules")}</h3>
            <ViewAllButton t={t} onClick={() => openViewAll("rules")} />
          </div>
          <BarList
            noDataLabel={t("common.noData")}
            rows={topRules.map((r) => ({
              label: `${r.rule_id} ${r.message ?? ""}`.trim(),
              count: r.count,
              href: `/logs?rule_id=${encodeURIComponent(r.rule_id)}`,
            }))}
          />
        </div>
        <div className="card">
          <div style={{ display: "flex", alignItems: "center" }}>
            <h3 style={{ marginRight: "auto" }}>{t("dashboard.topIps")}</h3>
            <ViewAllButton t={t} onClick={() => openViewAll("ips")} />
          </div>
          <BarList
            noDataLabel={t("common.noData")}
            rows={topIps.map((i) => ({
              label: i.ip,
              count: i.count,
              href: `/logs?client_ip=${encodeURIComponent(i.ip)}`,
            }))}
          />
        </div>
      </div>

      {viewAll && (
        <Modal title={viewAllTitle} onClose={() => setViewAll(null)}>
          {viewAllRows === null ? (
            <LoadingInline />
          ) : (
            <BarList noDataLabel={t("common.noData")} rows={viewAllRows} />
          )}
        </Modal>
      )}
    </div>
  );
}
