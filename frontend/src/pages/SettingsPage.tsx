import { useEffect, useState } from "react";
import { api, LogSink } from "../api/client";

const emptyForm = { name: "", protocol: "udp" as "udp" | "tcp", host: "", port: 514 };

export function SettingsPage() {
  const [sinks, setSinks] = useState<LogSink[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);

  function refresh() {
    api.listLogSinks().then(setSinks).catch((e) => setError(String(e)));
  }

  useEffect(refresh, []);

  async function submit() {
    if (!form.name.trim() || !form.host.trim()) return;
    try {
      await api.createLogSink(form);
      setForm(emptyForm);
      refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <div>
      <h2>Log Forwarding</h2>
      <p className="muted">
        Every enabled sink below gets a copy of each ModSecurity audit log entry, forwarded as a syslog message by
        the log-forwarder container. Audit log entries are always kept locally too (for the Logs page) regardless
        of this setting.
      </p>

      {error && <p>{error}</p>}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Protocol</th>
              <th>Host</th>
              <th>Port</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sinks.map((s) => (
              <tr key={s.id}>
                <td>{s.name}</td>
                <td>{s.protocol.toUpperCase()}</td>
                <td>{s.host}</td>
                <td>{s.port}</td>
                <td style={{ display: "flex", gap: 8 }}>
                  <button className="btn" onClick={() => api.toggleLogSink(s.id, !s.enabled).then(refresh)}>
                    {s.enabled ? "Disable" : "Enable"}
                  </button>
                  <button
                    className="btn"
                    onClick={() => {
                      if (confirm(`Delete sink "${s.name}"?`)) api.deleteLogSink(s.id).then(refresh);
                    }}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {sinks.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  No log sinks configured - logs stay local only.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>Add sink</h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input placeholder="Name (e.g. SIEM)" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <select value={form.protocol} onChange={(e) => setForm({ ...form, protocol: e.target.value as "udp" | "tcp" })}>
            <option value="udp">UDP</option>
            <option value="tcp">TCP</option>
          </select>
          <input placeholder="Host" value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })} />
          <input
            type="number"
            placeholder="Port"
            style={{ width: 100 }}
            value={form.port}
            onChange={(e) => setForm({ ...form, port: Number(e.target.value) })}
          />
          <button className="btn" onClick={submit}>
            Add sink
          </button>
        </div>
      </div>
    </div>
  );
}
