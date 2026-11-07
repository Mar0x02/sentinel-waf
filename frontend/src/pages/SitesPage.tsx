import { Check, Copy, Loader2, ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ApiError, CertOrder, api, Site, SitePayload } from "../api/client";
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

// Whole days until expiry, or null if there's no cert at all.
function daysUntilExpiry(site: Site): number | null {
  if (!site.cert_expires_at) return null;
  return Math.ceil((new Date(site.cert_expires_at).getTime() - Date.now()) / 86_400_000);
}

const RENEW_SOON_DAYS = 7;

function certBadge(site: Site, t: (key: string, vars?: Record<string, string | number>) => string) {
  if (!site.tls_enabled) return <span className="muted">{t("sites.tlsOff")}</span>;
  if (!site.has_cert) return <span className="tls-badge tls-badge-warn">{t("sites.tlsMissingCert")}</span>;
  const days = daysUntilExpiry(site);
  const expired = days !== null && days < 0;
  const expiringSoon = days !== null && days >= 0 && days <= RENEW_SOON_DAYS;
  const date = site.cert_expires_at ? new Date(site.cert_expires_at).toLocaleDateString() : "";
  return (
    <span className={`tls-badge ${expired ? "tls-badge-expired" : expiringSoon ? "tls-badge-warn" : "tls-badge-ok"}`}>
      {expired ? t("sites.tlsExpired") : t("sites.tlsValidUntil", { date, days: days ?? 0 })}
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
  const [certOrders, setCertOrders] = useState<Record<number, CertOrder>>({});
  // Tracks the in-flight startCertOrder() call itself (opening the ACME
  // order is a real network round-trip to Let's Encrypt, not instant) -
  // separate from certOrders' "pending_dns" status, which only starts
  // existing once that call has already returned.
  const [generating, setGenerating] = useState<Record<number, boolean>>({});
  // Which TXT value was just copied (its own text is a unique-enough key) -
  // swaps that one row's "Copy" link to a "Copied" checkmark for a bit.
  const [copiedValue, setCopiedValue] = useState<string | null>(null);
  // How many times we've polled for this site's order - purely cosmetic, so
  // the "checking..." line visibly ticks over each round instead of sitting
  // static while the 5s timer fires in the background.
  const [pollCount, setPollCount] = useState<Record<number, number>>({});
  const pollTimers = useRef<Record<number, number>>({});

  function copyValue(value: string) {
    navigator.clipboard.writeText(value);
    setCopiedValue(value);
    window.setTimeout(() => setCopiedValue((prev) => (prev === value ? null : prev)), 1500);
  }
  const certFileRef = useRef<HTMLInputElement>(null);
  const keyFileRef = useRef<HTMLInputElement>(null);

  function refresh() {
    api.listSites().then(setSites).catch((e) => toast.error(String(e)));
  }

  useEffect(refresh, []);

  // Stop every in-flight poll on unmount - otherwise a setTimeout chain
  // keeps firing against a torn-down component.
  useEffect(() => {
    return () => {
      Object.values(pollTimers.current).forEach((id) => window.clearTimeout(id));
    };
  }, []);

  function pollCertOrder(siteId: number) {
    api
      .getCertOrderStatus(siteId)
      .then((order) => {
        setCertOrders((prev) => ({ ...prev, [siteId]: order }));
        setPollCount((prev) => ({ ...prev, [siteId]: (prev[siteId] ?? 0) + 1 }));
        if (order.status === "pending_dns") {
          pollTimers.current[siteId] = window.setTimeout(() => pollCertOrder(siteId), 5000);
          return;
        }
        if (order.status === "issued") {
          toast.success(t("sites.certIssued"));
          refresh();
          // The edit form's "already stored, leave blank to keep it" hint
          // is driven by editingHasCert, captured once at startEdit() time -
          // flip it now too, so a cert that just got auto-issued while this
          // same form was open doesn't leave the form looking like nothing
          // happened (the PEM textareas themselves never get filled in from
          // the API either way - tls_cert/tls_key are write-only, same as
          // a manually-uploaded cert's fields would be on a re-edit).
          if (editingId === siteId) setEditingHasCert(true);
        } else {
          toast.error(order.error_message ?? t("sites.certFailed"));
        }
      })
      .catch((e) => toast.error(String(e)));
  }

  async function generateCert(siteId: number) {
    if (generating[siteId]) return; // already in flight - ignore a double-click
    // An order already pending means a TXT value is out there that a DNS
    // provider might still validate against - starting a fresh one (a new
    // CSR + a new token) makes that one stale. Not worth blocking outright
    // (sometimes the old one really is stuck and a restart is the fix,
    // like a wrong DNS record), but it shouldn't happen from one accidental
    // click, especially once this is pointed at production and each
    // restart counts against Let's Encrypt's weekly cert limit.
    if (certOrders[siteId]?.status === "pending_dns" && !(await confirm(t("sites.tlsRestartConfirm")))) {
      return;
    }
    window.clearTimeout(pollTimers.current[siteId]);
    setGenerating((prev) => ({ ...prev, [siteId]: true }));
    setPollCount((prev) => ({ ...prev, [siteId]: 0 }));
    api
      .startCertOrder(siteId)
      .then((order) => {
        setCertOrders((prev) => ({ ...prev, [siteId]: order }));
        pollTimers.current[siteId] = window.setTimeout(() => pollCertOrder(siteId), 5000);
      })
      .catch((e) => toast.error(String(e)))
      .finally(() => setGenerating((prev) => ({ ...prev, [siteId]: false })));
  }

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
                      {s.tls_enabled && s.has_cert && (() => {
                        const days = daysUntilExpiry(s);
                        return days !== null && days <= RENEW_SOON_DAYS;
                      })() && (
                        <button
                          className="btn"
                          disabled={generating[s.id]}
                          onClick={() => {
                            startEdit(s);
                            generateCert(s.id);
                          }}
                        >
                          {generating[s.id] ? t("common.loading") : t("sites.tlsRenewButton")}
                        </button>
                      )}
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
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  background: "rgba(34, 211, 238, 0.12)",
                  color: "#22d3ee",
                  border: "1px solid rgba(34, 211, 238, 0.3)",
                  borderRadius: 8,
                  padding: "10px 14px",
                  marginBottom: 10,
                  fontSize: 13,
                }}
              >
                <ShieldCheck size={16} style={{ flexShrink: 0 }} />
                <span>{t("sites.tlsKeepExistingHint")}</span>
              </div>
            )}

            {editingId !== null && (
              <div style={{ marginBottom: 12 }}>
                <button className="btn" disabled={generating[editingId]} onClick={() => generateCert(editingId)}>
                  {generating[editingId]
                    ? t("common.loading")
                    : editingHasCert
                      ? t("sites.tlsRenewButton")
                      : t("sites.tlsGenerateButton")}
                </button>
                {(certOrders[editingId]?.status === "pending_dns" || certOrders[editingId]?.status === "issued") && (
                  <div className="log-terminal" style={{ marginTop: 10 }}>
                    <div className="log-terminal-titlebar">
                      <span className="log-terminal-title">dns-01 · {form.domain}</span>
                    </div>
                    <div className="log-terminal-body">
                      <div className="log-terminal-line log-terminal-comment"># {t("sites.tlsPendingDns")}</div>
                      {([
                        ["TXT name", certOrders[editingId]!.dns_name],
                        ["TXT value", certOrders[editingId]!.dns_value],
                      ] as const).map(([label, value], i) => (
                        <div
                          className="log-terminal-line"
                          key={label}
                          style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: i === 0 ? 10 : 0 }}
                        >
                          <span className="log-terminal-prompt">$</span>
                          <span style={{ flexShrink: 0 }}>{label}=</span>
                          <span
                            className="log-terminal-value"
                            style={{ flex: 1, minWidth: 0, overflowX: "auto", whiteSpace: "pre" }}
                          >
                            {value}
                          </span>
                          <span
                            onClick={() => copyValue(value)}
                            style={{
                              flexShrink: 0,
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 4,
                              cursor: "pointer",
                              fontSize: 12,
                              color: copiedValue === value ? "#22c55e" : "#22d3ee",
                              textDecoration: copiedValue === value ? "none" : "underline",
                            }}
                          >
                            {copiedValue === value ? (
                              <>
                                <Check size={13} /> {t("common.copied")}
                              </>
                            ) : (
                              <>
                                <Copy size={13} /> {t("common.copy")}
                              </>
                            )}
                          </span>
                        </div>
                      ))}
                      {certOrders[editingId]?.status === "pending_dns" && (
                        <div className="log-terminal-line" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <Loader2 size={13} className="login-spinner" style={{ color: "#94a3b8" }} />
                          <span className="log-terminal-comment">
                            {t("sites.tlsChecking", { n: pollCount[editingId] ?? 0 })}
                          </span>
                        </div>
                      )}
                      {certOrders[editingId]?.status === "issued" && (
                        <div className="log-terminal-line" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <Check size={13} style={{ color: "#22c55e" }} />
                          <span style={{ color: "#22c55e" }}>{t("sites.tlsDnsVerified")}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
                {certOrders[editingId]?.status === "failed" && (
                  <p className="tls-badge tls-badge-expired" style={{ marginTop: 8 }}>
                    {certOrders[editingId]!.error_message}
                  </p>
                )}
              </div>
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
