import { useEffect, useState } from "react";
import { api, Site } from "../api/client";

const emptyForm = { name: "", domain: "", upstream_url: "", listen_port: 8080 };

export function SitesPage() {
  const [sites, setSites] = useState<Site[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);

  function refresh() {
    api.listSites().then(setSites).catch((e) => setError(String(e)));
  }

  useEffect(refresh, []);

  async function submit() {
    try {
      if (editingId !== null) {
        await api.updateSite(editingId, form);
      } else {
        await api.createSite(form);
      }
      setForm(emptyForm);
      setEditingId(null);
      refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  function startEdit(site: Site) {
    setEditingId(site.id);
    setForm({
      name: site.name,
      domain: site.domain,
      upstream_url: site.upstream_url,
      listen_port: site.listen_port,
    });
  }

  return (
    <div>
      <h2>Sites (Reverse Proxy)</h2>
      <p className="muted">
        Each enabled site becomes an nginx server block on the waf-engine container, protected by whatever rule
        sets are active on the Rules page. HTTP only for now - see README for TLS.
      </p>

      {error && <p>{error}</p>}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Domain</th>
              <th>Upstream</th>
              <th>Port</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sites.map((s) => (
              <tr key={s.id}>
                <td>{s.name}</td>
                <td>{s.domain}</td>
                <td>{s.upstream_url}</td>
                <td>{s.listen_port}</td>
                <td style={{ display: "flex", gap: 8 }}>
                  <button className="btn" onClick={() => startEdit(s)}>
                    Edit
                  </button>
                  <button className="btn" onClick={() => api.toggleSite(s.id, !s.enabled).then(refresh)}>
                    {s.enabled ? "Disable" : "Enable"}
                  </button>
                  <button
                    className="btn"
                    onClick={() => {
                      if (confirm(`Delete site "${s.name}"?`)) api.deleteSite(s.id).then(refresh);
                    }}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {sites.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  No sites yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>{editingId !== null ? "Edit site" : "Add site"}</h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input
            placeholder="Domain (e.g. shop.example.com)"
            value={form.domain}
            onChange={(e) => setForm({ ...form, domain: e.target.value })}
          />
          <input
            placeholder="Upstream (http://host:port)"
            style={{ flex: 1 }}
            value={form.upstream_url}
            onChange={(e) => setForm({ ...form, upstream_url: e.target.value })}
          />
          <input
            type="number"
            placeholder="Listen port"
            style={{ width: 110 }}
            value={form.listen_port}
            onChange={(e) => setForm({ ...form, listen_port: Number(e.target.value) })}
          />
          <button className="btn" onClick={submit}>
            {editingId !== null ? "Save" : "Add site"}
          </button>
          {editingId !== null && (
            <button
              className="btn"
              onClick={() => {
                setEditingId(null);
                setForm(emptyForm);
              }}
            >
              Cancel
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
