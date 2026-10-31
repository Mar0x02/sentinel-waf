import { useEffect, useState } from "react";
import { api, EngineSettings, engineSettingsApi, LogSink } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ChangePasswordForm } from "../components/ChangePasswordForm";
import { useLanguage } from "../i18n/LanguageContext";

const emptyForm = { name: "", protocol: "udp" as "udp" | "tcp", host: "", port: 514 };

function EngineSettingsCard() {
  const { t } = useLanguage();
  const [engine, setEngine] = useState<EngineSettings | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  function refresh() {
    engineSettingsApi.get().then(setEngine).catch((e) => setStatus(String(e)));
  }

  useEffect(refresh, []);

  async function save() {
    if (!engine) return;
    setStatus(null);
    try {
      const { updated_at, ...payload } = engine;
      const updated = await engineSettingsApi.update(payload);
      setEngine(updated);
      setStatus(t("engine.saveSuccess"));
    } catch (e) {
      setStatus(t("engine.saveError", { error: String(e) }));
    }
  }

  if (!engine) return null;

  return (
    <div className="card">
      <h3>{t("engine.title")}</h3>
      <p className="muted">{t("engine.description")}</p>
      {status && <p>{status}</p>}
      <div style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 480 }}>
        <label>
          {t("engine.auditEngine")}
          <select
            value={engine.audit_engine}
            onChange={(e) => setEngine({ ...engine, audit_engine: e.target.value as EngineSettings["audit_engine"] })}
            style={{ display: "block", marginTop: 4, width: "100%" }}
          >
            <option value="On">{t("engine.auditEngineOn")}</option>
            <option value="Off">{t("engine.auditEngineOff")}</option>
            <option value="RelevantOnly">{t("engine.auditEngineRelevant")}</option>
          </select>
        </label>
        <label>
          {t("engine.auditLogRelevantStatus")}
          <input
            value={engine.audit_log_relevant_status}
            onChange={(e) => setEngine({ ...engine, audit_log_relevant_status: e.target.value })}
            style={{ display: "block", marginTop: 4, width: "100%" }}
          />
          <span className="muted">{t("engine.auditLogRelevantStatusHint")}</span>
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <input
            type="checkbox"
            checked={engine.request_body_access}
            onChange={(e) => setEngine({ ...engine, request_body_access: e.target.checked })}
          />
          {t("engine.requestBodyAccess")}
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <input
            type="checkbox"
            checked={engine.response_body_access}
            onChange={(e) => setEngine({ ...engine, response_body_access: e.target.checked })}
          />
          {t("engine.responseBodyAccess")}
        </label>
        <label>
          {t("engine.requestBodyLimit")}
          <input
            type="number"
            value={engine.request_body_limit}
            onChange={(e) => setEngine({ ...engine, request_body_limit: Number(e.target.value) })}
            style={{ display: "block", marginTop: 4, width: "100%" }}
          />
        </label>
        <label>
          {t("engine.responseBodyLimit")}
          <input
            type="number"
            value={engine.response_body_limit}
            onChange={(e) => setEngine({ ...engine, response_body_limit: Number(e.target.value) })}
            style={{ display: "block", marginTop: 4, width: "100%" }}
          />
        </label>
        <label>
          {t("engine.responseBodyMimeType")}
          <input
            value={engine.response_body_mime_type}
            onChange={(e) => setEngine({ ...engine, response_body_mime_type: e.target.value })}
            style={{ display: "block", marginTop: 4, width: "100%" }}
          />
        </label>
        <button className="btn" onClick={save}>
          {t("engine.save")}
        </button>
      </div>
    </div>
  );
}

export function SettingsPage() {
  const { t } = useLanguage();
  const { isAdmin } = useAuth();
  const [sinks, setSinks] = useState<LogSink[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [passwordChanged, setPasswordChanged] = useState(false);

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
                  {isAdmin && (
                    <>
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
                    </>
                  )}
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

      {isAdmin && (
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
      )}

      {isAdmin && <EngineSettingsCard />}

      <h2>{t("auth.accountSection")}</h2>
      <div className="card">
        <p className="muted">{t("auth.changePasswordDesc")}</p>
        {passwordChanged ? (
          <p>{t("auth.changeSuccess")}</p>
        ) : (
          <ChangePasswordForm onSuccess={() => setPasswordChanged(true)} />
        )}
      </div>
    </div>
  );
}
