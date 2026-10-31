import { useEffect, useState } from "react";
import { api, Site } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useLanguage } from "../i18n/LanguageContext";

const emptyForm = { name: "", domain: "", upstream_url: "", listen_port: 8080 };

export function SitesPage() {
  const { t } = useLanguage();
  const { canWrite } = useAuth();
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
      <h2>{t("sites.title")}</h2>
      <p className="muted">{t("sites.description")}</p>

      {error && <p>{error}</p>}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>{t("sites.name")}</th>
              <th>{t("sites.domain")}</th>
              <th>{t("sites.upstream")}</th>
              <th>{t("sites.port")}</th>
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
                  {canWrite && (
                    <>
                      <button className="btn" onClick={() => startEdit(s)}>
                        {t("common.edit")}
                      </button>
                      <button className="btn" onClick={() => api.toggleSite(s.id, !s.enabled).then(refresh)}>
                        {s.enabled ? t("common.disable") : t("common.enable")}
                      </button>
                      <button
                        className="btn"
                        onClick={() => {
                          if (confirm(t("sites.deleteConfirm", { name: s.name }))) api.deleteSite(s.id).then(refresh);
                        }}
                      >
                        {t("common.delete")}
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
            {sites.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  {t("sites.noSites")}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {canWrite && (
      <div className="card">
        <h3>{editingId !== null ? t("sites.editSite") : t("sites.addSite")}</h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input
            placeholder={t("sites.namePlaceholder")}
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <input
            placeholder={t("sites.domainPlaceholder")}
            value={form.domain}
            onChange={(e) => setForm({ ...form, domain: e.target.value })}
          />
          <input
            placeholder={t("sites.upstreamPlaceholder")}
            style={{ flex: 1 }}
            value={form.upstream_url}
            onChange={(e) => setForm({ ...form, upstream_url: e.target.value })}
          />
          <input
            type="number"
            placeholder={t("sites.listenPortPlaceholder")}
            style={{ width: 110 }}
            value={form.listen_port}
            onChange={(e) => setForm({ ...form, listen_port: Number(e.target.value) })}
          />
          <button className="btn" onClick={submit}>
            {editingId !== null ? t("common.save") : t("sites.addSite")}
          </button>
          {editingId !== null && (
            <button
              className="btn"
              onClick={() => {
                setEditingId(null);
                setForm(emptyForm);
              }}
            >
              {t("common.cancel")}
            </button>
          )}
        </div>
      </div>
      )}
    </div>
  );
}
