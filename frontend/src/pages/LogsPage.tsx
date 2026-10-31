import { useEffect, useState } from "react";
import { api, AuditLogEntry } from "../api/client";

export function LogsPage() {
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
      <h2>Audit Logs</h2>
      <div className="filters-row">
        <input
          placeholder="Filter by rule ID"
          value={ruleId}
          onChange={(e) => {
            setOffset(0);
            setRuleId(e.target.value);
          }}
        />
        <input
          placeholder="Filter by client IP"
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
          Blocked only
        </label>
      </div>

      {error && <p>Gagal memuat log: {error}</p>}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Client IP</th>
              <th>Method</th>
              <th>URI</th>
              <th>Status</th>
              <th>Matched rules</th>
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
                    {entry.blocked ? "Blocked" : entry.status_code ?? "-"}
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
                  Tidak ada entry.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button className="btn" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>
          Prev
        </button>
        <span className="muted">
          {offset + 1}-{Math.min(offset + limit, total)} of {total}
        </span>
        <button className="btn" disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)}>
          Next
        </button>
      </div>
    </div>
  );
}
