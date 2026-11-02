import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, DiscordWebhook, discordApi, EngineSettings, engineSettingsApi, LogSink } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ChangePasswordForm } from "../components/ChangePasswordForm";
import { useConfirm } from "../components/ConfirmProvider";
import { useLanguage } from "../i18n/LanguageContext";

const emptyForm = { name: "", protocol: "udp" as "udp" | "tcp", host: "", port: 514 };
const emptyDiscordForm = { name: "", webhook_url: "" };

function DiscordWebhooksCard() {
  const { t } = useLanguage();
  const confirm = useConfirm();
  const [webhooks, setWebhooks] = useState<DiscordWebhook[]>([]);
  const [form, setForm] = useState(emptyDiscordForm);

  function refresh() {
    discordApi.list().then(setWebhooks).catch((e) => toast.error(String(e)));
  }

  useEffect(refresh, []);

  async function submit() {
    if (!form.name.trim() || !form.webhook_url.trim()) return;
    try {
      await discordApi.create(form.name, form.webhook_url);
      toast.success(t("discord.addSuccess", { name: form.name }));
      setForm(emptyDiscordForm);
      refresh();
    } catch (e) {
      toast.error(String(e));
    }
  }

  return (
    <div className="card">
      <h3>{t("discord.title")}</h3>
      <p className="muted">{t("discord.description")}</p>
      <table>
        <thead>
          <tr>
            <th>{t("discord.name")}</th>
            <th>{t("discord.webhookUrl")}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {webhooks.map((w) => (
            <tr key={w.id}>
              <td>{w.name}</td>
              <td style={{ maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {w.webhook_url}
              </td>
              <td style={{ display: "flex", gap: 8 }}>
                <button
                  className="btn"
                  onClick={() =>
                    discordApi
                      .toggle(w.id, !w.enabled)
                      .then(refresh)
                      .catch((e) => toast.error(String(e)))
                  }
                >
                  {w.enabled ? t("common.disable") : t("common.enable")}
                </button>
                <button
                  className="btn btn-danger"
                  onClick={async () => {
                    if (await confirm(t("discord.deleteConfirm", { name: w.name }))) {
                      discordApi
                        .delete(w.id)
                        .then(() => {
                          toast.success(t("discord.deleteSuccess", { name: w.name }));
                          refresh();
                        })
                        .catch((e) => toast.error(String(e)));
                    }
                  }}
                >
                  {t("common.delete")}
                </button>
              </td>
            </tr>
          ))}
          {webhooks.length === 0 && (
            <tr>
              <td colSpan={3} className="muted">
                {t("discord.noWebhooks")}
              </td>
            </tr>
          )}
        </tbody>
      </table>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
        <input
          placeholder={t("discord.namePlaceholder")}
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
        />
        <input
          placeholder={t("discord.urlPlaceholder")}
          style={{ flex: 1, minWidth: 240 }}
          value={form.webhook_url}
          onChange={(e) => setForm({ ...form, webhook_url: e.target.value })}
        />
        <button className="btn btn-primary" onClick={submit}>
          {t("discord.addWebhook")}
        </button>
      </div>
    </div>
  );
}

function EngineSettingsCard() {
  const { t } = useLanguage();
  const [engine, setEngine] = useState<EngineSettings | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

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
      <div className="engine-grid">
        <label>
          {t("engine.auditEngine")}
          <select
            value={engine.audit_engine}
            onChange={(e) => setEngine({ ...engine, audit_engine: e.target.value as EngineSettings["audit_engine"] })}
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
          />
          <span className="muted">{t("engine.auditLogRelevantStatusHint")}</span>
        </label>
        <label className="engine-checkbox">
          <input
            type="checkbox"
            checked={engine.request_body_access}
            onChange={(e) => setEngine({ ...engine, request_body_access: e.target.checked })}
          />
          {t("engine.requestBodyAccess")}
        </label>
        <label className="engine-checkbox">
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
          />
        </label>
        <label>
          {t("engine.responseBodyLimit")}
          <input
            type="number"
            value={engine.response_body_limit}
            onChange={(e) => setEngine({ ...engine, response_body_limit: Number(e.target.value) })}
          />
        </label>
        <label className="engine-span-2">
          {t("engine.responseBodyMimeType")}
          <input
            value={engine.response_body_mime_type}
            onChange={(e) => setEngine({ ...engine, response_body_mime_type: e.target.value })}
          />
        </label>
      </div>

      <button className="btn" style={{ marginTop: 14 }} onClick={() => setShowAdvanced(!showAdvanced)}>
        {showAdvanced ? `▾ ${t("engine.advancedTitle")}` : `▸ ${t("engine.advancedToggle")}`}
      </button>
      {showAdvanced && (
        <div style={{ marginTop: 10 }}>
          <p className="muted">{t("engine.advancedDesc")}</p>
          <textarea
            className="rule-editor engine-advanced-editor"
            placeholder={t("engine.advancedPlaceholder")}
            value={engine.advanced_config}
            onChange={(e) => setEngine({ ...engine, advanced_config: e.target.value })}
          />
        </div>
      )}

      <button className="btn btn-primary" style={{ marginTop: 14 }} onClick={save}>
        {t("engine.save")}
      </button>
    </div>
  );
}

export function SettingsPage() {
  const { t } = useLanguage();
  const { isAdmin } = useAuth();
  const confirm = useConfirm();
  const [sinks, setSinks] = useState<LogSink[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [passwordChanged, setPasswordChanged] = useState(false);

  function refresh() {
    api.listLogSinks().then(setSinks).catch((e) => toast.error(String(e)));
  }

  useEffect(refresh, []);

  async function submit() {
    if (!form.name.trim() || !form.host.trim()) return;
    try {
      await api.createLogSink(form);
      toast.success(t("settings.addSinkSuccess", { name: form.name }));
      setForm(emptyForm);
      refresh();
    } catch (e) {
      toast.error(String(e));
    }
  }

  return (
    <div>
      <h2>{t("settings.title")}</h2>
      <p className="muted">{t("settings.description")}</p>

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
                      <button
                        className="btn"
                        onClick={() =>
                          api
                            .toggleLogSink(s.id, !s.enabled)
                            .then(refresh)
                            .catch((e) => toast.error(String(e)))
                        }
                      >
                        {s.enabled ? t("common.disable") : t("common.enable")}
                      </button>
                      <button
                        className="btn btn-danger"
                        onClick={async () => {
                          if (await confirm(t("settings.deleteConfirm", { name: s.name }))) {
                            api
                              .deleteLogSink(s.id)
                              .then(() => {
                                toast.success(t("settings.deleteSinkSuccess", { name: s.name }));
                                refresh();
                              })
                              .catch((e) => toast.error(String(e)));
                          }
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
            <button className="btn btn-primary" onClick={submit}>
              {t("settings.addSink")}
            </button>
          </div>
        </div>
      )}

      {isAdmin && <DiscordWebhooksCard />}
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
