import { useEffect, useState } from "react";
import { api, LogSink } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";

const emptyForm = { name: "", protocol: "udp" as "udp" | "tcp", host: "", port: 514 };

export function SettingsPage() {
  const { t } = useLanguage();
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
      <h2>{t("settings.title")}</h2>
      <p className="muted">{t("settings.description")}</p>

      {error && <p>{error}</p>}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>{t("settings.name")}</th>
              <th>{t("settings.protocol")}</th>
              <th>{t("settings.host")}</th>
              <th>{t("settings.port")}</th>
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
                    {s.enabled ? t("common.disable") : t("common.enable")}
                  </button>
                  <button
                    className="btn"
                    onClick={() => {
                      if (confirm(t("settings.deleteConfirm", { name: s.name }))) api.deleteLogSink(s.id).then(refresh);
                    }}
                  >
                    {t("common.delete")}
                  </button>
                </td>
              </tr>
            ))}
            {sinks.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  {t("settings.noSinks")}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>{t("settings.addSink")}</h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input
            placeholder={t("settings.namePlaceholder")}
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <select value={form.protocol} onChange={(e) => setForm({ ...form, protocol: e.target.value as "udp" | "tcp" })}>
            <option value="udp">UDP</option>
            <option value="tcp">TCP</option>
          </select>
          <input
            placeholder={t("settings.hostPlaceholder")}
            value={form.host}
            onChange={(e) => setForm({ ...form, host: e.target.value })}
          />
          <input
            type="number"
            placeholder={t("settings.portPlaceholder")}
            style={{ width: 100 }}
            value={form.port}
            onChange={(e) => setForm({ ...form, port: Number(e.target.value) })}
          />
          <button className="btn" onClick={submit}>
            {t("settings.addSink")}
          </button>
        </div>
      </div>
    </div>
  );
}
