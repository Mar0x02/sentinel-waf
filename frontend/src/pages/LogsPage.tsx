import { Fragment, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { api, AuditLogEntry } from "../api/client";
import { CATEGORY_COLORS } from "../components/CategoryTrendChart";
import { useLanguage } from "../i18n/LanguageContext";

// ModSecurity logs severity as a raw syslog-style number - lower is worse
// (0=Emergency, 1=Alert, 2=Critical, ...), the opposite of what "severity
// 2" reads like at a glance. Shown as a label so it doesn't look like a
// minor/low-priority match.
const SEVERITY_LABELS: Record<string, string> = {
  "0": "EMERGENCY",
  "1": "ALERT",
  "2": "CRITICAL",
  "3": "ERROR",
  "4": "WARNING",
  "5": "NOTICE",
  "6": "INFO",
  "7": "DEBUG",
};

function severityLabel(severity: string | null): string {
  if (!severity) return "-";
  const label = SEVERITY_LABELS[severity];
  return label ? `${label} (${severity})` : severity;
}

export function LogsPage() {
  const { t } = useLanguage();
  const [searchParams] = useSearchParams();
  const [items, setItems] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  // Pre-filled when arriving from a Dashboard "top rules"/"top IPs"/"top
  // categories" link (e.g. /logs?rule_id=941100) - read once on mount, not
  // kept in sync with further typing, same as every other filter here.
  const [ruleId, setRuleId] = useState(() => searchParams.get("rule_id") ?? "");
  const [clientIp, setClientIp] = useState(() => searchParams.get("client_ip") ?? "");
  const [category, setCategory] = useState(() => searchParams.get("category") ?? "");
  const [blockedOnly, setBlockedOnly] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const limit = 25;

  useEffect(() => {
    api
      .listLogs({
        limit,
        offset,
        rule_id: ruleId || undefined,
        client_ip: clientIp || undefined,
        category: category || undefined,
        blocked_only: blockedOnly,
      })
      .then((page) => {
        setItems(page.items);
        setTotal(page.total);
      })
      .catch((e) => toast.error(t("logs.loadError", { error: String(e) })));
  }, [offset, ruleId, clientIp, category, blockedOnly]);

  return (
    <div>
      <h2>{t("logs.title")}</h2>
      <div className="filters-row">
        <input
          placeholder={t("logs.filterRuleId")}
          value={ruleId}
          onChange={(e) => {
            setOffset(0);
            setRuleId(e.target.value);
          }}
        />
        <input
          placeholder={t("logs.filterClientIp")}
          value={clientIp}
          onChange={(e) => {
            setOffset(0);
            setClientIp(e.target.value);
          }}
        />
        <select
          value={category}
          onChange={(e) => {
            setOffset(0);
            setCategory(e.target.value);
          }}
        >
          <option value="">{t("logs.filterCategoryAll")}</option>
          {Object.keys(CATEGORY_COLORS).map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
          {category && !(category in CATEGORY_COLORS) && <option value={category}>{category}</option>}
        </select>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
          <input
            type="checkbox"
            checked={blockedOnly}
            onChange={(e) => {
              setOffset(0);
              setBlockedOnly(e.target.checked);
            }}
          />
          {t("logs.blockedOnly")}
        </label>
      </div>

      <p className="muted" style={{ fontSize: 12 }}>
        {t("logs.detailHint")}
      </p>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>{t("logs.timestamp")}</th>
              <th>{t("logs.clientIp")}</th>
              <th>{t("logs.host")}</th>
              <th>{t("logs.method")}</th>
              <th>{t("logs.uri")}</th>
              <th>{t("logs.status")}</th>
              <th>{t("logs.matchedRules")}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((entry) => {
              const isExpanded = expandedId === entry.transaction_id;
              return (
                <Fragment key={entry.transaction_id}>
                  <tr
                    onClick={() => setExpandedId(isExpanded ? null : entry.transaction_id)}
                    style={{ cursor: "pointer" }}
                  >
                    <td>{entry.timestamp ?? "-"}</td>
                    <td>{entry.client_ip ?? "-"}</td>
                    <td>{entry.host ?? "-"}</td>
                    <td>{entry.method ?? "-"}</td>
                    <td style={{ maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis" }}>
                      {entry.uri ?? "-"}
                    </td>
                    <td>
                      <span className={`pill ${entry.blocked ? "blocked" : "ok"}`}>
                        {entry.blocked ? t("logs.blockedPill") : entry.status_code ?? "-"}
                      </span>
                    </td>
                    <td>
                      {entry.matches.length === 0
                        ? "-"
                        : entry.matches.map((m) => m.rule_id).join(", ")}
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr>
                      <td colSpan={7} className="log-detail-cell">
                        <div className="log-terminal">
                          <div className="log-terminal-titlebar">
                            <span className="log-terminal-title">{entry.transaction_id}</span>
                          </div>
                          <div className="log-terminal-body">
                            <div className="log-terminal-line">
                              <span className="log-terminal-prompt">$</span> {t("logs.transactionId")}=
                              <span className="log-terminal-value">{entry.transaction_id}</span>
                            </div>
                            <div className="log-terminal-line">
                              <span className="log-terminal-prompt">$</span> {t("logs.userAgent")}=
                              <span className="log-terminal-value">{entry.user_agent ?? "-"}</span>
                            </div>
                            {Object.keys(entry.headers).length > 0 && (
                              <>
                                <div className="log-terminal-line log-terminal-comment"># {t("logs.headers")}</div>
                                {Object.entries(entry.headers).map(([name, value]) => (
                                  <div className="log-terminal-line log-terminal-indent" key={name}>
                                    {name}: <span className="log-terminal-value">{value}</span>
                                  </div>
                                ))}
                              </>
                            )}
                            {entry.matches.length === 0 ? (
                              <div className="log-terminal-line log-terminal-comment"># {t("logs.noMatches")}</div>
                            ) : (
                              <>
                                <div className="log-terminal-line log-terminal-comment"># {t("logs.matchedRules")}</div>
                                {entry.matches.map((m, idx) => (
                                  <div className="log-terminal-match" key={`${entry.transaction_id}-match-${idx}`}>
                                    <div className="log-terminal-line">
                                      <span className="log-terminal-rule">[{m.rule_id ?? "-"}]</span>{" "}
                                      {m.message ?? ""}
                                    </div>
                                    <div className="log-terminal-line log-terminal-indent log-terminal-comment">
                                      {t("logs.matchSeverity")}={severityLabel(m.severity)} {t("logs.matchTags")}=
                                      {m.tags.join(",") || "-"}
                                    </div>
                                    {m.data && (
                                      <div className="log-terminal-line log-terminal-indent log-terminal-data">
                                        {t("logs.matchData")}: {m.data}
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
            {items.length === 0 && (
              <tr>
                <td colSpan={7} className="muted">
                  {t("logs.noEntries")}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button className="btn" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>
          {t("logs.prev")}
        </button>
        <span className="muted">
          {t("logs.range", { from: offset + 1, to: Math.min(offset + limit, total), total })}
        </span>
        <button className="btn" disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)}>
          {t("logs.next")}
        </button>
      </div>
    </div>
  );
}
