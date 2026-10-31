import { useEffect, useState } from "react";
import { api, AuditLogEntry } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";

export function LogsPage() {
  const { t } = useLanguage();
  const [items, setItems] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [ruleId, setRuleId] = useState("");
  const [clientIp, setClientIp] = useState("");
  const [blockedOnly, setBlockedOnly] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const limit = 25;

  useEffect(() => {
    api
      .listLogs({ limit, offset, rule_id: ruleId || undefined, client_ip: clientIp || undefined, blocked_only: blockedOnly })
      .then((page) => {
        setItems(page.items);
        setTotal(page.total);
      })
      .catch((e) => setError(String(e)));
  }, [offset, ruleId, clientIp, blockedOnly]);

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

      {error && <p>{t("logs.loadError", { error })}</p>}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>{t("logs.timestamp")}</th>
              <th>{t("logs.clientIp")}</th>
              <th>{t("logs.method")}</th>
              <th>{t("logs.uri")}</th>
              <th>{t("logs.status")}</th>
              <th>{t("logs.matchedRules")}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((entry) => (
              <tr key={entry.transaction_id}>
                <td>{entry.timestamp ?? "-"}</td>
                <td>{entry.client_ip ?? "-"}</td>
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
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={6} className="muted">
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
