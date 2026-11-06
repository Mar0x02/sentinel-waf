import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api, IpRule, ipRulesApi } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useConfirm } from "../components/ConfirmProvider";
import { Modal } from "../components/Modal";
import { useLanguage } from "../i18n/LanguageContext";

const emptyForm = { ip: "", action: "block" as "allow" | "block", note: "" };

export function AccessControlPage() {
  const { t } = useLanguage();
  const { canWrite } = useAuth();
  const confirm = useConfirm();
  const [tab, setTab] = useState<"block" | "allow">("block");
  const [rules, setRules] = useState<IpRule[]>([]);
  const [hits, setHits] = useState<Record<string, number>>({});
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const visibleRules = rules.filter((r) => r.action === tab);

  function refresh() {
    ipRulesApi
      .list()
      .then((list) => {
        setRules(list);
        // One lightweight count query per IP, reusing the existing Logs
        // endpoint's client_ip filter + total - no separate aggregation
        // endpoint needed (see render_service.render_ip_rules()'s
        // log,auditlog, which is what makes these hits show up at all).
        list.forEach((rule) => {
          api
            .listLogs({ client_ip: rule.ip, limit: 1 })
            .then((page) => setHits((prev) => ({ ...prev, [rule.ip]: page.total })))
            .catch(() => {});
        });
      })
      .catch((e) => toast.error(String(e)));
  }

  useEffect(refresh, []);

  async function submit() {
    if (!form.ip.trim()) return;
    try {
      await ipRulesApi.create(form.ip.trim(), form.action, form.note.trim());
      toast.success(t("accessControl.addSuccess", { ip: form.ip.trim() }));
      setForm(emptyForm);
      setAddOpen(false);
      refresh();
    } catch (e) {
      toast.error(String(e));
    }
  }

  return (
    <div>
      <h2>{t("accessControl.title")}</h2>
      <p className="muted">{t(tab === "block" ? "accessControl.blockDescription" : "accessControl.allowDescription")}</p>

      <div style={{ display: "flex", gap: 8, marginBottom: 12, justifyContent: "space-between", flexWrap: "wrap" }}>
        <div style={{ display: "flex", gap: 8 }}>
          <button className={`btn ${tab === "block" ? "btn-primary" : ""}`} onClick={() => setTab("block")}>
            {t("accessControl.block")} ({rules.filter((r) => r.action === "block").length})
          </button>
          <button className={`btn ${tab === "allow" ? "btn-primary" : ""}`} onClick={() => setTab("allow")}>
            {t("accessControl.allow")} ({rules.filter((r) => r.action === "allow").length})
          </button>
        </div>
        {canWrite && (
          <button
            className="btn btn-primary"
            onClick={() => {
              setForm({ ...emptyForm, action: tab });
              setAddOpen(true);
            }}
          >
            {t("accessControl.addRule")}
          </button>
        )}
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>{t("accessControl.ip")}</th>
              <th>{t("accessControl.note")}</th>
              <th>{t("accessControl.hits")}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {visibleRules.map((rule) => (
              <tr key={rule.id} style={{ opacity: rule.enabled ? 1 : 0.5 }}>
                <td>{rule.ip}</td>
                <td>{rule.note ?? "-"}</td>
                <td>
                  <Link to={`/logs?client_ip=${encodeURIComponent(rule.ip)}`}>
                    {hits[rule.ip] ?? "-"} {t("accessControl.viewLogs")}
                  </Link>
                </td>
                <td style={{ display: "flex", gap: 8 }}>
                  {canWrite && (
                    <>
                      <button
                        className="btn"
                        onClick={() =>
                          ipRulesApi
                            .toggle(rule.id, !rule.enabled)
                            .then(refresh)
                            .catch((e) => toast.error(String(e)))
                        }
                      >
                        {rule.enabled ? t("common.disable") : t("common.enable")}
                      </button>
                      <button
                        className="btn btn-danger"
                        onClick={async () => {
                          if (await confirm(t("accessControl.deleteConfirm", { ip: rule.ip }))) {
                            ipRulesApi
                              .delete(rule.id)
                              .then(() => {
                                toast.success(t("accessControl.deleteSuccess", { ip: rule.ip }));
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
            {visibleRules.length === 0 && (
              <tr>
                <td colSpan={4} className="muted">
                  {t("accessControl.noRules")}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {addOpen && (
        <Modal title={t("accessControl.addRule")} onClose={() => setAddOpen(false)}>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <select value={form.action} onChange={(e) => setForm({ ...form, action: e.target.value as "allow" | "block" })}>
              <option value="block">{t("accessControl.block")}</option>
              <option value="allow">{t("accessControl.allow")}</option>
            </select>
            <input
              autoFocus
              placeholder={t("accessControl.ipPlaceholder")}
              value={form.ip}
              onChange={(e) => setForm({ ...form, ip: e.target.value })}
            />
            <input
              placeholder={t("accessControl.notePlaceholder")}
              value={form.note}
              onChange={(e) => setForm({ ...form, note: e.target.value })}
            />
            <button className="btn btn-primary" onClick={submit}>
              {t("common.save")}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
