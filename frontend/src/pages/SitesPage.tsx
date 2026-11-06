import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ApiError, api, Site, SitePayload } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useConfirm } from "../components/ConfirmProvider";
import { useLanguage } from "../i18n/LanguageContext";

const emptyForm = {
  name: "",
  domain: "",
  upstream_url: "",
  listen_port: 8080,
  tls_enabled: false,
  tls_listen_port: 8443,
  tls_cert: "",
  tls_key: "",
  rate_limit_enabled: false,
  rate_limit_rps: 20,
  rate_limit_burst: 40,
  conn_limit_enabled: false,
  conn_limit_per_ip: 50,
  // Anti-bot toggles are edited on the dedicated Anti-Bot page, not here -
  // these are only carried through untouched so a plain edit of
  // name/domain/etc via this form doesn't reset them back to off.
  bot_challenge_enabled: false,
  honeypot_checkbox_enabled: false,
  honeypot_path_enabled: false,
  block_bad_user_agents: false,
};

function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

function certBadge(site: Site, t: (key: string, vars?: Record<string, string | number>) => string) {
  if (!site.tls_enabled) return <span className="muted">{t("sites.tlsOff")}</span>;
  if (!site.has_cert) return <span className="tls-badge tls-badge-warn">{t("sites.tlsMissingCert")}</span>;
  const expires = site.cert_expires_at ? new Date(site.cert_expires_at) : null;
  const expired = expires !== null && expires.getTime() < Date.now();
  return (
    <span className={`tls-badge ${expired ? "tls-badge-expired" : "tls-badge-ok"}`}>
      {expired ? t("sites.tlsExpired") : t("sites.tlsValidUntil", { date: expires?.toLocaleDateString() ?? "" })}
    </span>
  );
}

function limitBadge(site: Site, t: (key: string, vars?: Record<string, string | number>) => string) {
  if (!site.rate_limit_enabled && !site.conn_limit_enabled) return <span className="muted">{t("sites.tlsOff")}</span>;
  const parts: string[] = [];
  if (site.rate_limit_enabled) parts.push(t("sites.rateLimitBadge", { rps: site.rate_limit_rps }));
  if (site.conn_limit_enabled) parts.push(t("sites.connLimitBadge", { n: site.conn_limit_per_ip }));
  return <span className="tls-badge tls-badge-ok">{parts.join(" · ")}</span>;
}

export function SitesPage() {
  const { t } = useLanguage();
  const { canWrite } = useAuth();
  const confirm = useConfirm();
  const [sites, setSites] = useState<Site[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingHasCert, setEditingHasCert] = useState(false);
  const certFileRef = useRef<HTMLInputElement>(null);
  const keyFileRef = useRef<HTMLInputElement>(null);

  function refresh() {
    api.listSites().then(setSites).catch((e) => toast.error(String(e)));
  }

  useEffect(refresh, []);

  async function submit() {
    const payload: SitePayload = {
      name: form.name,
      domain: form.domain,
      upstream_url: form.upstream_url,
      listen_port: form.listen_port,
      tls_enabled: form.tls_enabled,
      tls_listen_port: form.tls_listen_port,
      rate_limit_enabled: form.rate_limit_enabled,
      rate_limit_rps: form.rate_limit_rps,
      rate_limit_burst: form.rate_limit_burst,
      conn_limit_enabled: form.conn_limit_enabled,
      conn_limit_per_ip: form.conn_limit_per_ip,
      bot_challenge_enabled: form.bot_challenge_enabled,
      honeypot_checkbox_enabled: form.honeypot_checkbox_enabled,
      honeypot_path_enabled: form.honeypot_path_enabled,
      block_bad_user_agents: form.block_bad_user_agents,
    };
    // Only send a cert/key pair if the operator actually pasted/uploaded
    // one this time - omitting both tells the backend to keep whatever is
    // already stored (see SitePayload). The textareas are never
    // pre-filled with an existing key (write-only, same as a password).
    if (form.tls_cert.trim() && form.tls_key.trim()) {
      payload.tls_cert = form.tls_cert.trim();
      payload.tls_key = form.tls_key.trim();
    }
    setFieldErrors({});
    try {
      if (editingId !== null) {
        await api.updateSite(editingId, payload);
        toast.success(t("sites.saveSuccess", { name: form.name }));
      } else {
        await api.createSite(payload);
        toast.success(t("sites.addSuccess", { name: form.name }));
      }
      setForm(emptyForm);
      setEditingId(null);
      setEditingHasCert(false);
      refresh();
    } catch (e) {
      if (e instanceof ApiError) setFieldErrors(e.fields);
      toast.error(String(e));
    }
  }

  function startEdit(site: Site) {
    setEditingId(site.id);
    setEditingHasCert(site.has_cert);
    setForm({
      name: site.name,
      domain: site.domain,
      upstream_url: site.upstream_url,
      listen_port: site.listen_port,
      tls_enabled: site.tls_enabled,
      tls_listen_port: site.tls_listen_port,
      tls_cert: "",
      tls_key: "",
      rate_limit_enabled: site.rate_limit_enabled,
      rate_limit_rps: site.rate_limit_rps,
      rate_limit_burst: site.rate_limit_burst,
      conn_limit_enabled: site.conn_limit_enabled,
      conn_limit_per_ip: site.conn_limit_per_ip,
      bot_challenge_enabled: site.bot_challenge_enabled,
      honeypot_checkbox_enabled: site.honeypot_checkbox_enabled,
      honeypot_path_enabled: site.honeypot_path_enabled,
      block_bad_user_agents: site.block_bad_user_agents,
    });
  }

  return (
    <div>
      <h2>{t("sites.title")}</h2>
      <p className="muted">{t("sites.description")}</p>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>{t("sites.name")}</th>
              <th>{t("sites.domain")}</th>
              <th>{t("sites.upstream")}</th>
              <th>{t("sites.port")}</th>
              <th>{t("sites.tlsColumn")}</th>
              <th>{t("sites.limitsColumn")}</th>
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
                <td>{certBadge(s, t)}</td>
                <td>{limitBadge(s, t)}</td>
                <td style={{ display: "flex", gap: 8 }}>
                  {canWrite && (
                    <>
                      <button className="btn" onClick={() => startEdit(s)}>
                        {t("common.edit")}
                      </button>
                      <button
                        className="btn"
                        onClick={() =>
                          api
                            .toggleSite(s.id, !s.enabled)
                            .then(refresh)
                            .catch((e) => toast.error(String(e)))
                        }
                      >
                        {s.enabled ? t("common.disable") : t("common.enable")}
                      </button>
                      <button
                        className="btn btn-danger"
                        onClick={async () => {
                          if (await confirm(t("sites.deleteConfirm", { name: s.name }))) {
                            api
                              .deleteSite(s.id)
                              .then(() => {
                                toast.success(t("sites.deleteSuccess", { name: s.name }));
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
            {sites.length === 0 && (
              <tr>
                <td colSpan={7} className="muted">
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
            className={fieldErrors.name ? "input-error" : ""}
            placeholder={t("sites.namePlaceholder")}
            value={form.name}
            onChange={(e) => {
              setFieldErrors({ ...fieldErrors, name: "" });
              setForm({ ...form, name: e.target.value });
            }}
          />
          <input
            className={fieldErrors.domain ? "input-error" : ""}
            placeholder={t("sites.domainPlaceholder")}
            value={form.domain}
            onChange={(e) => {
              setFieldErrors({ ...fieldErrors, domain: "" });
              setForm({ ...form, domain: e.target.value });
            }}
          />
          <input
            className={fieldErrors.upstream_url ? "input-error" : ""}
            placeholder={t("sites.upstreamPlaceholder")}
            style={{ flex: 1 }}
            value={form.upstream_url}
            onChange={(e) => {
              setFieldErrors({ ...fieldErrors, upstream_url: "" });
              setForm({ ...form, upstream_url: e.target.value });
            }}
          />
          <input
            className={fieldErrors.listen_port ? "input-error" : ""}
            type="number"
            placeholder={t("sites.listenPortPlaceholder")}
            style={{ width: 110 }}
            value={form.listen_port}
            onChange={(e) => {
              setFieldErrors({ ...fieldErrors, listen_port: "" });
              setForm({ ...form, listen_port: Number(e.target.value) });
            }}
          />
        </div>

        <label className="toggle-option toggle-option-first">
          <input
            type="checkbox"
            checked={form.tls_enabled}
            onChange={(e) => setForm({ ...form, tls_enabled: e.target.checked })}
          />
          {t("sites.tlsEnable")}
        </label>

        {form.tls_enabled && (
          <div className="tls-form" style={{ marginTop: 10 }}>
            <p className="muted">{t("sites.tlsDescription")}</p>
            {editingId !== null && editingHasCert && (
              <p className="muted">{t("sites.tlsKeepExistingHint")}</p>
            )}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <label style={{ minWidth: 90 }}>{t("sites.tlsPort")}</label>
              <input
                type="number"
                style={{ width: 110 }}
                value={form.tls_listen_port}
                onChange={(e) => setForm({ ...form, tls_listen_port: Number(e.target.value) })}
              />
            </div>

            <div className="tls-pem-row">
              <div className="tls-pem-field">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                  <label>{t("sites.tlsCertLabel")}</label>
                  <button className="btn" onClick={() => certFileRef.current?.click()}>
                    {t("sites.tlsUploadFile")}
                  </button>
                </div>
                <input
                  ref={certFileRef}
                  type="file"
                  accept=".crt,.pem,.cer"
                  style={{ display: "none" }}
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (file) setForm({ ...form, tls_cert: await readFileAsText(file) });
                    e.target.value = "";
                  }}
                />
                <textarea
                  className="rule-editor"
                  rows={5}
                  placeholder={
                    editingHasCert ? t("sites.tlsCertPlaceholderKeep") : "-----BEGIN CERTIFICATE-----"
                  }
                  value={form.tls_cert}
                  onChange={(e) => setForm({ ...form, tls_cert: e.target.value })}
                />
              </div>
              <div className="tls-pem-field">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                  <label>{t("sites.tlsKeyLabel")}</label>
                  <button className="btn" onClick={() => keyFileRef.current?.click()}>
                    {t("sites.tlsUploadFile")}
                  </button>
                </div>
                <input
                  ref={keyFileRef}
                  type="file"
                  accept=".key,.pem"
                  style={{ display: "none" }}
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (file) setForm({ ...form, tls_key: await readFileAsText(file) });
                    e.target.value = "";
                  }}
                />
                <textarea
                  className="rule-editor"
                  rows={5}
                  placeholder={
                    editingHasCert ? t("sites.tlsKeyPlaceholderKeep") : "-----BEGIN PRIVATE KEY-----"
                  }
                  value={form.tls_key}
                  onChange={(e) => setForm({ ...form, tls_key: e.target.value })}
                />
              </div>
            </div>
          </div>
        )}

        <label className="toggle-option">
          <input
            type="checkbox"
            checked={form.rate_limit_enabled}
            onChange={(e) => setForm({ ...form, rate_limit_enabled: e.target.checked })}
          />
          {t("sites.rateLimitEnable")}
        </label>
        {form.rate_limit_enabled && (
          <div className="tls-form" style={{ marginTop: 8 }}>
            <p className="muted">{t("sites.rateLimitDescription")}</p>
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {t("sites.rateLimitRps")}
                <input
                  type="number"
                  style={{ width: 90 }}
                  value={form.rate_limit_rps}
                  onChange={(e) => setForm({ ...form, rate_limit_rps: Number(e.target.value) })}
                />
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {t("sites.rateLimitBurst")}
                <input
                  type="number"
                  style={{ width: 90 }}
                  value={form.rate_limit_burst}
                  onChange={(e) => setForm({ ...form, rate_limit_burst: Number(e.target.value) })}
                />
              </label>
            </div>
          </div>
        )}

        <label className="toggle-option">
          <input
            type="checkbox"
            checked={form.conn_limit_enabled}
            onChange={(e) => setForm({ ...form, conn_limit_enabled: e.target.checked })}
          />
          {t("sites.connLimitEnable")}
        </label>
        {form.conn_limit_enabled && (
          <div className="tls-form" style={{ marginTop: 8 }}>
            <p className="muted">{t("sites.connLimitDescription")}</p>
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {t("sites.connLimitPerIp")}
              <input
                type="number"
                style={{ width: 90 }}
                value={form.conn_limit_per_ip}
                onChange={(e) => setForm({ ...form, conn_limit_per_ip: Number(e.target.value) })}
              />
            </label>
          </div>
        )}

        <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
          <button className="btn btn-primary" onClick={submit}>
            {editingId !== null ? t("common.save") : t("sites.addSite")}
          </button>
          {editingId !== null && (
            <button
              className="btn"
              onClick={() => {
                setEditingId(null);
                setForm(emptyForm);
                setFieldErrors({});
                setEditingHasCert(false);
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
