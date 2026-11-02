import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, ErrorPage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useConfirm } from "../components/ConfirmProvider";
import { useLanguage } from "../i18n/LanguageContext";

export function ErrorPagesPage() {
  const { t } = useLanguage();
  const { canWrite } = useAuth();
  const confirm = useConfirm();
  const [pages, setPages] = useState<ErrorPage[]>([]);
  const [editing, setEditing] = useState<{ statusCode: number; html: string } | null>(null);

  function refresh() {
    api.listErrorPages().then(setPages).catch((e) => toast.error(String(e)));
  }

  useEffect(refresh, []);

  function startEdit(page: ErrorPage) {
    setEditing({ statusCode: page.status_code, html: page.html_content });
  }

  async function save() {
    if (!editing) return;
    try {
      await api.updateErrorPage(editing.statusCode, editing.html);
      toast.success(t("errorPages.saveSuccess", { code: editing.statusCode }));
      setEditing(null);
      refresh();
    } catch (e) {
      toast.error(String(e));
    }
  }

  async function reset(statusCode: number) {
    if (!(await confirm(t("errorPages.resetConfirm", { code: statusCode })))) return;
    try {
      await api.resetErrorPage(statusCode);
      toast.success(t("errorPages.resetSuccess", { code: statusCode }));
      if (editing?.statusCode === statusCode) setEditing(null);
      refresh();
    } catch (e) {
      toast.error(String(e));
    }
  }

  return (
    <div>
      <h2>{t("errorPages.title")}</h2>
      <p className="muted">{t("errorPages.description")}</p>

      <div className="card">
        {pages.map((p) => (
          <div className="rule-file-row" key={p.status_code}>
            <div>
              <strong>{p.status_code}</strong> - {p.title}{" "}
              <span className={`pill ${p.is_customized ? "blocked" : "ok"}`}>
                {p.is_customized ? t("errorPages.customized") : t("errorPages.default")}
              </span>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              {canWrite && (
                <>
                  <button className="btn" onClick={() => startEdit(p)}>
                    {t("common.edit")}
                  </button>
                  <button className="btn" disabled={!p.is_customized} onClick={() => reset(p.status_code)}>
                    {t("errorPages.resetToDefault")}
                  </button>
                </>
              )}
            </div>
          </div>
        ))}
      </div>

      {editing && (
        <div className="card">
          <h3>{t("errorPages.editingPage", { code: editing.statusCode })}</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div>
              <p className="muted">{t("errorPages.html")}</p>
              <textarea
                className="rule-editor"
                style={{ minHeight: 320, fontSize: 12 }}
                value={editing.html}
                onChange={(e) => setEditing({ ...editing, html: e.target.value })}
              />
            </div>
            <div>
              <p className="muted">{t("errorPages.preview")}</p>
              <iframe
                title="preview"
                srcDoc={editing.html}
                sandbox=""
                style={{ width: "100%", minHeight: 320, border: "1px solid var(--border)", borderRadius: 6, background: "#fff" }}
              />
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <button className="btn btn-primary" onClick={save}>
              {t("common.save")}
            </button>
            <button className="btn" onClick={() => setEditing(null)}>
              {t("common.cancel")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
