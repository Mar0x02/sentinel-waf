import { useEffect, useState } from "react";
import { api, CatalogEntry, CrsTuning, RuleFile, RuleRow, RuleSet } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useLanguage } from "../i18n/LanguageContext";

function CrsTuningPanel({ ruleSetId }: { ruleSetId: number }) {
  const { t } = useLanguage();
  const { canWrite } = useAuth();
  const [tuning, setTuning] = useState<CrsTuning | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    api.getTuning(ruleSetId).then(setTuning).catch(() => setTuning(null));
  }, [ruleSetId]);

  async function save() {
    if (!tuning) return;
    setStatus(null);
    try {
      const updated = await api.updateTuning(ruleSetId, tuning);
      setTuning(updated);
      setStatus(t("tuning.saveSuccess"));
    } catch (e) {
      setStatus(t("tuning.saveError", { error: String(e) }));
    }
  }

  if (!tuning) return null;

  return (
    <div className="card">
      <h3>{t("tuning.title")}</h3>
      <p className="muted">{t("tuning.description")}</p>
      {status && <p>{status}</p>}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, maxWidth: 480 }}>
        <label>
          {t("tuning.blockingParanoia")}
          <select
            value={tuning.blocking_paranoia_level}
            onChange={(e) => setTuning({ ...tuning, blocking_paranoia_level: Number(e.target.value) })}
            style={{ display: "block", marginTop: 4, width: "100%" }}
            disabled={!canWrite}
          >
            {[1, 2, 3, 4].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("tuning.detectionParanoia")}
          <select
            value={tuning.detection_paranoia_level}
            onChange={(e) => setTuning({ ...tuning, detection_paranoia_level: Number(e.target.value) })}
            style={{ display: "block", marginTop: 4, width: "100%" }}
            disabled={!canWrite}
          >
            {[1, 2, 3, 4].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
          <span className="muted">{t("tuning.detectionParanoiaHint")}</span>
        </label>
        <label>
          {t("tuning.inboundThreshold")}
          <input
            type="number"
            value={tuning.inbound_anomaly_score_threshold}
            onChange={(e) => setTuning({ ...tuning, inbound_anomaly_score_threshold: Number(e.target.value) })}
            style={{ display: "block", marginTop: 4, width: "100%" }}
            disabled={!canWrite}
          />
        </label>
        <label>
          {t("tuning.outboundThreshold")}
          <input
            type="number"
            value={tuning.outbound_anomaly_score_threshold}
            onChange={(e) => setTuning({ ...tuning, outbound_anomaly_score_threshold: Number(e.target.value) })}
            style={{ display: "block", marginTop: 4, width: "100%" }}
            disabled={!canWrite}
          />
        </label>
      </div>
      {canWrite && (
        <button className="btn" style={{ marginTop: 12 }} onClick={save}>
          {t("tuning.save")}
        </button>
      )}
    </div>
  );
}

function RuleFilesPanel({ ruleSet, onChanged }: { ruleSet: RuleSet; onChanged: () => void }) {
  const { t } = useLanguage();
  const { canWrite } = useAuth();
  const [files, setFiles] = useState<RuleFile[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<{ id: number; filename: string; content: string } | null>(null);
  const [rulesOf, setRulesOf] = useState<{ fileId: number; rows: RuleRow[] } | null>(null);
  const [newFilename, setNewFilename] = useState("");
  const isCustom = ruleSet.slug === "custom";

  function refresh() {
    api.listRuleFiles(ruleSet.id).then(setFiles).catch((e) => setError(String(e)));
  }

  useEffect(refresh, [ruleSet.id]);

  async function openEditor(file: RuleFile) {
    const { content } = await api.readRuleFile(file.id);
    setEditing({ id: file.id, filename: file.filename, content });
  }

  async function saveEditor() {
    if (!editing) return;
    await api.updateRuleFile(editing.id, editing.content);
    setEditing(null);
    refresh();
    onChanged();
  }

  async function openRules(file: RuleFile) {
    const rows = await api.listRules({ rule_file_id: file.id, limit: 200 });
    setRulesOf({ fileId: file.id, rows });
  }

  async function createFile() {
    if (!newFilename.trim()) return;
    const filename = newFilename.endsWith(".conf") ? newFilename : `${newFilename}.conf`;
    await api.createRuleFile(filename, "# new rule file\n");
    setNewFilename("");
    refresh();
    onChanged();
  }

  const hasSetupFile = files.some((f) => f.file_kind === "setup");

  return (
    <>
      {hasSetupFile && <CrsTuningPanel ruleSetId={ruleSet.id} />}
      <div className="card" style={{ marginTop: 8 }}>
      {error && <p>{error}</p>}
      {files
        .filter((f) => f.file_kind !== "asset")
        .map((f) => (
          <div className="rule-file-row" key={f.id}>
            <div>
              <strong>{f.filename}</strong>{" "}
              <span className="muted">
                {t("rules.ruleCount", { count: f.rule_count })} · {f.size_bytes} bytes{" "}
                {f.file_kind === "setup" && t("rules.setupFile")}
              </span>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn" onClick={() => openRules(f)}>
                {t("rules.viewRules")}
              </button>
              {(isCustom || f.file_kind === "setup") && canWrite && (
                <button className="btn" onClick={() => openEditor(f)}>
                  {t("common.edit")}
                </button>
              )}
              {canWrite && (
                <button className="btn" onClick={() => api.toggleRuleFile(f.id, !f.enabled).then(() => { refresh(); onChanged(); })}>
                  {f.enabled ? t("common.disable") : t("common.enable")}
                </button>
              )}
              {isCustom && canWrite && (
                <button
                  className="btn"
                  onClick={() => {
                    if (confirm(t("rules.deleteFileConfirm", { filename: f.filename }))) {
                      api.deleteRuleFile(f.id).then(() => { refresh(); onChanged(); });
                    }
                  }}
                >
                  {t("common.delete")}
                </button>
              )}
            </div>
          </div>
        ))}
      {files.filter((f) => f.file_kind !== "asset").length === 0 && (
        <p className="muted">{t("rules.noRuleFiles")}</p>
      )}

      {isCustom && canWrite && (
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <input
            placeholder={t("rules.newFilePlaceholder")}
            value={newFilename}
            onChange={(e) => setNewFilename(e.target.value)}
          />
          <button className="btn" onClick={createFile}>
            {t("rules.newFile")}
          </button>
        </div>
      )}

      {editing && (
        <div className="card">
          <h3>{t("rules.editingFile", { filename: editing.filename })}</h3>
          <textarea
            className="rule-editor"
            value={editing.content}
            onChange={(e) => setEditing({ ...editing, content: e.target.value })}
          />
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button className="btn" onClick={saveEditor}>
              {t("common.save")}
            </button>
            <button className="btn" onClick={() => setEditing(null)}>
              {t("common.cancel")}
            </button>
          </div>
        </div>
      )}

      {rulesOf && (
        <div className="card">
          <h3>{t("rules.rulesInFile")}</h3>
          <table>
            <thead>
              <tr>
                <th>{t("rules.id")}</th>
                <th>{t("rules.message")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rulesOf.rows.map((r) => (
                <tr key={r.id}>
                  <td>{r.rule_id ?? "-"}</td>
                  <td>{r.message ?? "-"}</td>
                  <td>
                    {canWrite && (
                      <button
                        className="btn"
                        disabled={!r.rule_id}
                        onClick={() =>
                          api.toggleRule(r.id, !r.enabled).then(() => {
                            openRules(files.find((f) => f.id === rulesOf.fileId)!);
                            onChanged();
                          })
                        }
                      >
                        {r.enabled ? t("common.disable") : t("common.enable")}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {rulesOf.rows.length === 0 && (
                <tr>
                  <td colSpan={3} className="muted">
                    {t("rules.noParsedRules")}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <button className="btn" style={{ marginTop: 8 }} onClick={() => setRulesOf(null)}>
            {t("common.close")}
          </button>
        </div>
      )}
      </div>
    </>
  );
}

export function RulesPage() {
  const { t } = useLanguage();
  const { canWrite } = useAuth();
  const [ruleSets, setRuleSets] = useState<RuleSet[]>([]);
  const [catalog, setCatalog] = useState<CatalogEntry[]>([]);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [urlName, setUrlName] = useState("");
  const [urlUrl, setUrlUrl] = useState("");

  function refresh() {
    api.listRuleSets().then(setRuleSets).catch((e) => setError(String(e)));
  }

  useEffect(() => {
    refresh();
    api.listCatalog().then(setCatalog).catch((e) => setError(String(e)));
  }, []);

  async function doImportCatalog(id: string) {
    setBusy(true);
    setError(null);
    try {
      await api.importCatalog(id);
      refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function doImportUrl() {
    if (!urlName.trim() || !urlUrl.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.importUrl(urlName, urlUrl);
      setUrlName("");
      setUrlUrl("");
      refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h2>{t("rules.title")}</h2>
      {error && <p>{error}</p>}

      {canWrite && (
        <div className="card">
          <h3>{t("rules.importCrsTitle")}</h3>
          {catalog.map((entry) => {
            const imported = ruleSets.some((rs) => rs.source_url === entry.url);
            return (
              <div className="rule-file-row" key={entry.id}>
                <div>
                  <strong>
                    {entry.name} {entry.version}
                  </strong>
                  <div className="muted">{entry.description}</div>
                </div>
                <button className="btn" disabled={busy || imported} onClick={() => doImportCatalog(entry.id)}>
                  {imported ? t("rules.imported") : busy ? t("rules.importing") : t("rules.import")}
                </button>
              </div>
            );
          })}
        </div>
      )}

      {canWrite && (
        <div className="card">
          <h3>{t("rules.importUrlTitle")}</h3>
          <p className="muted">{t("rules.importUrlDesc")}</p>
          <div style={{ display: "flex", gap: 8 }}>
            <input placeholder={t("rules.namePlaceholder")} value={urlName} onChange={(e) => setUrlName(e.target.value)} />
            <input
              placeholder={t("rules.urlPlaceholder")}
              style={{ flex: 1 }}
              value={urlUrl}
              onChange={(e) => setUrlUrl(e.target.value)}
            />
            <button className="btn" disabled={busy} onClick={doImportUrl}>
              {t("rules.import")}
            </button>
          </div>
        </div>
      )}

      <h2>{t("rules.installedTitle")}</h2>
      {ruleSets.map((rs) => (
        <div className="card" key={rs.id}>
          <div className="rule-file-row" style={{ borderBottom: "none" }}>
            <div>
              <strong>{rs.name}</strong> {rs.version && <span className="muted">v{rs.version}</span>}{" "}
              <span className="muted">
                · {t("rules.fileCount", { count: rs.file_count })} · {t("rules.ruleCount", { count: rs.rule_count })} ·{" "}
                {rs.source_type}
              </span>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn" onClick={() => setExpanded(expanded === rs.id ? null : rs.id)}>
                {expanded === rs.id ? t("rules.hideFiles") : t("rules.showFiles")}
              </button>
              {canWrite && (
                <button className="btn" onClick={() => api.toggleRuleSet(rs.id, !rs.enabled).then(refresh)}>
                  {rs.enabled ? t("common.disable") : t("common.enable")}
                </button>
              )}
              {canWrite && rs.slug !== "custom" && (
                <button
                  className="btn"
                  onClick={() => {
                    if (confirm(t("rules.deleteSetConfirm", { name: rs.name }))) {
                      api.deleteRuleSet(rs.id).then(refresh);
                    }
                  }}
                >
                  {t("common.delete")}
                </button>
              )}
            </div>
          </div>
          {expanded === rs.id && <RuleFilesPanel ruleSet={rs} onChanged={refresh} />}
        </div>
      ))}
    </div>
  );
}
