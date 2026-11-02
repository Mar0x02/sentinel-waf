import { Fragment, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  api,
  CrsTuning,
  RuleFile,
  RuleFileVersion,
  RuleRow,
  RuleSet,
  TunableFix,
  TunableGroup,
  TxVarWarning,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useConfirm } from "../components/ConfirmProvider";
import { LoadingInline } from "../components/LoadingShield";
import { Modal } from "../components/Modal";
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
      <div className="tuning-grid">
        <label>
          {t("tuning.blockingParanoia")}
          <select
            value={tuning.blocking_paranoia_level}
            onChange={(e) => setTuning({ ...tuning, blocking_paranoia_level: Number(e.target.value) })}
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
            disabled={!canWrite}
          />
        </label>
        <label>
          {t("tuning.outboundThreshold")}
          <input
            type="number"
            value={tuning.outbound_anomaly_score_threshold}
            onChange={(e) => setTuning({ ...tuning, outbound_anomaly_score_threshold: Number(e.target.value) })}
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

function TunableRow({ ruleSetId, group }: { ruleSetId: number; group: TunableGroup }) {
  const { t } = useLanguage();
  const { canWrite } = useAuth();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(group.is_active);
  const [variables, setVariables] = useState(group.variables);
  const [status, setStatus] = useState<string | null>(null);

  async function save() {
    setStatus(null);
    try {
      await api.updateTunable(ruleSetId, group.rule_id, active, variables);
      setStatus(t("tunables.saveSuccess"));
    } catch (e) {
      setStatus(t("tunables.saveError", { error: String(e) }));
    }
  }

  const preview = Object.entries(group.variables)
    .map(([name, value]) => `${name}=${value}`)
    .join(", ");

  return (
    <div className="tunable-row">
      <div className="tunable-summary" onClick={() => setOpen(!open)}>
        <span className="tunable-chevron">{open ? "▾" : "▸"}</span>
        <strong>id:{group.rule_id}</strong>
        {group.description && <span className="muted"> · {group.description}</span>}
        <span className="muted tunable-preview"> · {preview}</span>
        <label
          className="tunable-active"
          onClick={(e) => e.stopPropagation()}
          style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}
        >
          <input type="checkbox" checked={active} disabled={!canWrite} onChange={(e) => setActive(e.target.checked)} />
          {t("tunables.active")}
        </label>
      </div>
      {open && (
        <div className="tunable-detail">
          {status && <p className="muted">{status}</p>}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {Object.entries(variables).map(([name, value]) => (
              <label key={name} style={{ fontSize: 12 }}>
                {name}
                <input
                  value={value}
                  disabled={!canWrite}
                  onChange={(e) => setVariables({ ...variables, [name]: e.target.value })}
                  style={{ display: "block", marginTop: 2 }}
                />
              </label>
            ))}
            {canWrite && (
              <button className="btn" style={{ alignSelf: "flex-end" }} onClick={save}>
                {t("tunables.save")}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function TunablesPanel({ ruleSetId }: { ruleSetId: number }) {
  const { t } = useLanguage();
  const [groups, setGroups] = useState<TunableGroup[] | null>(null);

  useEffect(() => {
    api.listTunables(ruleSetId).then(setGroups).catch(() => setGroups([]));
  }, [ruleSetId]);

  if (groups === null) return null;

  return (
    <div className="card">
      <h3>{t("tunables.title")}</h3>
      <p className="muted">{t("tunables.description")}</p>
      {groups.length === 0 && <p className="muted">{t("tunables.none")}</p>}
      {groups.map((g) => (
        <TunableRow key={g.rule_id} ruleSetId={ruleSetId} group={g} />
      ))}
    </div>
  );
}

function fixButtonLabel(fix: TunableFix, t: (key: string, vars?: Record<string, string | number>) => string) {
  if (fix.init_collection) {
    return t("rules.lintInitCollectionFix", { collection: fix.init_collection, ruleSetName: fix.rule_set_name });
  }
  return fix.is_new
    ? t("rules.lintCreateFix", { variable: Object.keys(fix.variables)[0] ?? "", ruleSetName: fix.rule_set_name })
    : t("rules.lintActivateFix", { tunableId: fix.tunable_rule_id, ruleSetName: fix.rule_set_name });
}

function warningMessage(w: TxVarWarning, t: (key: string, vars?: Record<string, string | number>) => string) {
  if (w.kind === "uninitialized_collection") {
    return t("rules.lintUninitializedCollection", { variable: w.variable, ruleId: w.rule_id ?? "?" });
  }
  if (w.kind === "unused_counter") {
    return t("rules.lintUnusedCounter", { variable: w.variable, ruleId: w.rule_id ?? "?" });
  }
  return t("rules.lintUndefinedVar", { variable: w.variable, ruleId: w.rule_id ?? "?" });
}

export function RuleSetDetailPage() {
  const { ruleSetId } = useParams<{ ruleSetId: string }>();
  const id = Number(ruleSetId);
  const navigate = useNavigate();
  const { t } = useLanguage();
  const { canWrite } = useAuth();
  const confirm = useConfirm();

  const [ruleSet, setRuleSet] = useState<RuleSet | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [files, setFiles] = useState<RuleFile[]>([]);
  const [editing, setEditing] = useState<{ id: number; filename: string; content: string } | null>(null);
  const [rulesOf, setRulesOf] = useState<{
    fileId: number;
    filename: string;
    rows: RuleRow[];
    warnings: TxVarWarning[];
  } | null>(null);
  const [expandedRuleId, setExpandedRuleId] = useState<number | null>(null);
  const [newFilename, setNewFilename] = useState("");
  const [lintWarnings, setLintWarnings] = useState<TxVarWarning[]>([]);
  const [checkingSave, setCheckingSave] = useState(false);
  const [saveConfirm, setSaveConfirm] = useState<TxVarWarning[] | null>(null);
  const [historyOf, setHistoryOf] = useState<{ fileId: number; filename: string; versions: RuleFileVersion[] } | null>(
    null
  );
  const [previewVersionId, setPreviewVersionId] = useState<number | null>(null);
  const [syncVersion, setSyncVersion] = useState(0);

  const isCustom = ruleSet?.slug === "custom";

  function refreshRuleSet() {
    api
      .getRuleSet(id)
      .then(setRuleSet)
      .catch(() => setNotFound(true));
  }

  function refreshFiles() {
    api.listRuleFiles(id).then(setFiles).catch((e) => toast.error(String(e)));
  }

  useEffect(() => {
    if (!Number.isFinite(id)) return;
    refreshRuleSet();
    refreshFiles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Advisory-only tx.* lint, debounced while typing - never blocks Save,
  // see backend/app/services/tx_var_linter.py.
  useEffect(() => {
    if (!editing) {
      setLintWarnings([]);
      return;
    }
    const handle = setTimeout(() => {
      api
        .lintRuleFile(editing.content, editing.id)
        .then((r) => setLintWarnings(r.warnings))
        .catch(() => {});
    }, 400);
    return () => clearTimeout(handle);
  }, [editing?.content, editing?.id]);

  async function activateFix(fix: TunableFix) {
    try {
      if (fix.init_collection) {
        await api.initCollection(fix.rule_set_id, fix.tunable_rule_id, fix.init_collection, 1);
        toast.success(
          t("rules.lintInitCollectionSuccess", { collection: fix.init_collection, ruleSetName: fix.rule_set_name })
        );
      } else if (fix.is_new) {
        await api.createTunable(fix.rule_set_id, fix.tunable_rule_id, 1, fix.variables);
        toast.success(t("rules.lintFixCreateSuccess", { ruleId: fix.tunable_rule_id, ruleSetName: fix.rule_set_name }));
      } else {
        await api.updateTunable(fix.rule_set_id, fix.tunable_rule_id, true, fix.variables);
        toast.success(t("rules.lintFixSuccess", { ruleId: fix.tunable_rule_id }));
      }
      refreshFiles();
      if (editing) {
        api
          .lintRuleFile(editing.content, editing.id)
          .then((r) => setLintWarnings(r.warnings))
          .catch(() => {});
      }
      if (rulesOf) {
        const updated = await api.listRuleFiles(id);
        const match = updated.find((f) => f.id === rulesOf.fileId);
        if (match) setRulesOf({ ...rulesOf, warnings: match.warnings });
      }
      if (saveConfirm && editing) {
        const { warnings } = await api.lintRuleFile(editing.content, editing.id);
        setSaveConfirm(warnings);
      }
    } catch (e) {
      toast.error(String(e));
    }
  }

  async function doSyncFromBaseTuning() {
    try {
      const applied = await api.syncFromBaseTuning(id);
      if (applied.length === 0) {
        toast(t("rules.syncNothingToDo"));
      } else {
        toast.success(t("rules.syncSuccess", { count: applied.length, ids: applied.join(", ") }));
      }
      refreshFiles();
      setSyncVersion((v) => v + 1);
    } catch (e) {
      toast.error(String(e));
    }
  }

  async function openEditor(file: RuleFile) {
    const { content } = await api.readRuleFile(file.id);
    setEditing({ id: file.id, filename: file.filename, content });
  }

  async function performSave() {
    if (!editing) return;
    try {
      await api.updateRuleFile(editing.id, editing.content);
      toast.success(t("rules.saveSuccess", { filename: editing.filename }));
      setEditing(null);
      setSaveConfirm(null);
      refreshFiles();
      refreshRuleSet();
    } catch (e) {
      toast.error(String(e));
    }
  }

  async function requestSave() {
    if (!editing) return;
    setCheckingSave(true);
    try {
      const { warnings } = await api.lintRuleFile(editing.content, editing.id);
      // Small deliberate pause so "Checking..." actually reads as a step,
      // not a flicker - the lint call itself is usually well under 100ms.
      await new Promise((r) => setTimeout(r, 400));
      if (warnings.length === 0) {
        await performSave();
      } else {
        setSaveConfirm(warnings);
      }
    } catch (e) {
      toast.error(String(e));
    } finally {
      setCheckingSave(false);
    }
  }

  async function openRules(file: RuleFile) {
    const rows = await api.listRules({ rule_file_id: file.id, limit: 200 });
    setRulesOf({ fileId: file.id, filename: file.filename, rows, warnings: file.warnings });
    setExpandedRuleId(null);
  }

  async function openHistory(file: RuleFile) {
    const versions = await api.listRuleFileVersions(file.id);
    setHistoryOf({ fileId: file.id, filename: file.filename, versions });
    setPreviewVersionId(null);
  }

  async function doRevert(version: RuleFileVersion) {
    if (!historyOf) return;
    const date = new Date(version.created_at).toLocaleString();
    if (!(await confirm(t("rules.revertConfirm", { filename: historyOf.filename, date })))) return;
    try {
      await api.revertRuleFile(historyOf.fileId, version.id);
      toast.success(t("rules.revertSuccess", { filename: historyOf.filename }));
      setHistoryOf(null);
      refreshFiles();
      refreshRuleSet();
    } catch (e) {
      toast.error(String(e));
    }
  }

  async function createFile() {
    if (!newFilename.trim()) return;
    const filename = newFilename.endsWith(".conf") ? newFilename : `${newFilename}.conf`;
    try {
      await api.createRuleFile(filename, "# new rule file\n");
      toast.success(t("rules.newFileSuccess", { filename }));
      setNewFilename("");
      refreshFiles();
      refreshRuleSet();
    } catch (e) {
      toast.error(String(e));
    }
  }

  if (notFound) {
    return (
      <div>
        <p>{t("rules.notFound")}</p>
        <Link className="btn" to="/rules">
          {t("rules.title")}
        </Link>
      </div>
    );
  }

  if (!ruleSet) return <LoadingInline />;

  const setupFile = files.find((f) => f.file_kind === "setup") ?? null;

  const editorPanel = editing && (
    <div className="card">
      <h3>{t("rules.editingFile", { filename: editing.filename })}</h3>
      <textarea
        className="rule-editor"
        value={editing.content}
        onChange={(e) => setEditing({ ...editing, content: e.target.value })}
      />
      {lintWarnings.length > 0 && (
        <div className="lint-warnings">
          <strong>{t("rules.lintTitle")}</strong>
          <ul>
            {lintWarnings.map((w, i) => (
              <li key={i}>
                {warningMessage(w, t)}
                {w.fix && (
                  <button className="btn lint-fix-btn" onClick={() => activateFix(w.fix!)}>
                    {fixButtonLabel(w.fix, t)}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <button className="btn" onClick={requestSave} disabled={checkingSave}>
          {checkingSave ? t("rules.checkingDependencies") : t("common.save")}
        </button>
        <button className="btn" onClick={() => setEditing(null)} disabled={checkingSave}>
          {t("common.cancel")}
        </button>
      </div>
    </div>
  );

  return (
    <div>
      <div className="breadcrumb">
        <Link to="/rules">{t("rules.title")}</Link>
        <span> / </span>
        <span>{ruleSet.name}</span>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="rule-file-row" style={{ borderBottom: "none" }}>
          <div>
            <strong>{ruleSet.name}</strong> {ruleSet.version && <span className="muted">v{ruleSet.version}</span>}{" "}
            <span className="muted">
              · {t("rules.fileCount", { count: ruleSet.file_count })} · {t("rules.ruleCount", { count: ruleSet.rule_count })} ·{" "}
              {ruleSet.source_type}
            </span>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            {canWrite && (
              <button
                className="btn"
                onClick={() =>
                  api
                    .toggleRuleSet(ruleSet.id, !ruleSet.enabled)
                    .then(refreshRuleSet)
                    .catch((e) => toast.error(String(e)))
                }
              >
                {ruleSet.enabled ? t("common.disable") : t("common.enable")}
              </button>
            )}
            {canWrite && ruleSet.slug !== "custom" && (
              <button
                className="btn btn-danger"
                onClick={async () => {
                  if (await confirm(t("rules.deleteSetConfirm", { name: ruleSet.name }))) {
                    api
                      .deleteRuleSet(ruleSet.id)
                      .then(() => {
                        toast.success(t("rules.deleteSetSuccess", { name: ruleSet.name }));
                        navigate("/rules");
                      })
                      .catch((e) => toast.error(String(e)));
                  }
                }}
              >
                {t("common.delete")}
              </button>
            )}
          </div>
        </div>
      </div>

      {setupFile && (
        <>
          <div className="card setup-file-bar">
            <div>
              <strong>{setupFile.filename}</strong>{" "}
              <span className="muted">{setupFile.size_bytes} bytes</span>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              {canWrite && ruleSet.slug !== "base-tuning" && (
                <button className="btn" title={t("rules.syncFromBaseTuningHint")} onClick={doSyncFromBaseTuning}>
                  {t("rules.syncFromBaseTuning")}
                </button>
              )}
              {canWrite && (
                <button className="btn" onClick={() => openEditor(setupFile)}>
                  {t("common.edit")}
                </button>
              )}
              <button className="btn" onClick={() => openHistory(setupFile)}>
                {t("rules.history")}
              </button>
            </div>
          </div>
          {editing && editing.id === setupFile.id && editorPanel}
          <CrsTuningPanel key={syncVersion} ruleSetId={ruleSet.id} />
          <TunablesPanel key={syncVersion} ruleSetId={ruleSet.id} />
        </>
      )}

      <div className="card">
        {files
          .filter((f) => f.file_kind !== "asset" && f.file_kind !== "setup")
          .map((f) => (
            <div className="rule-file-row" key={f.id}>
              <div>
                <strong>{f.filename}</strong>{" "}
                <span className="muted">
                  {t("rules.ruleCount", { count: f.rule_count })} · {f.size_bytes} bytes
                </span>
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button className="btn" onClick={() => openRules(f)}>
                  {t("rules.viewRules")}
                </button>
                {isCustom && canWrite && (
                  <button className="btn" onClick={() => openEditor(f)}>
                    {t("common.edit")}
                  </button>
                )}
                {canWrite && (
                  <button
                    className="btn"
                    onClick={() =>
                      api
                        .toggleRuleFile(f.id, !f.enabled)
                        .then(() => {
                          refreshFiles();
                          refreshRuleSet();
                        })
                        .catch((e) => toast.error(String(e)))
                    }
                  >
                    {f.enabled ? t("common.disable") : t("common.enable")}
                  </button>
                )}
                {isCustom && canWrite && (
                  <button
                    className="btn btn-danger"
                    onClick={async () => {
                      if (await confirm(t("rules.deleteFileConfirm", { filename: f.filename }))) {
                        api
                          .deleteRuleFile(f.id)
                          .then(() => {
                            toast.success(t("rules.deleteFileSuccess", { filename: f.filename }));
                            refreshFiles();
                            refreshRuleSet();
                          })
                          .catch((e) => toast.error(String(e)));
                      }
                    }}
                  >
                    {t("common.delete")}
                  </button>
                )}
              </div>
            </div>
          ))}
        {files.filter((f) => f.file_kind !== "asset" && f.file_kind !== "setup").length === 0 && (
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

        {editing && editing.id !== setupFile?.id && editorPanel}
      </div>

      {rulesOf && (
        <Modal title={t("rules.rulesInFileTitle", { filename: rulesOf.filename })} onClose={() => setRulesOf(null)}>
          {rulesOf.warnings.length > 0 && (
            <div className="lint-warnings">
              <strong>{t("rules.lintTitle")}</strong>
              <ul>
                {rulesOf.warnings.map((w, i) => (
                  <li key={i}>
                    {warningMessage(w, t)}
                    {w.fix && (
                      <button className="btn lint-fix-btn" onClick={() => activateFix(w.fix!)}>
                        {fixButtonLabel(w.fix, t)}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <table>
            <thead>
              <tr>
                <th></th>
                <th>{t("rules.id")}</th>
                <th>{t("rules.message")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rulesOf.rows.map((r) => {
                const isNoop = /\bnolog\b/i.test(r.raw_snippet);
                const expanded = expandedRuleId === r.id;
                return (
                  <Fragment key={r.id}>
                    <tr>
                      <td>
                        <button
                          className="rule-snippet-toggle"
                          onClick={() => setExpandedRuleId(expanded ? null : r.id)}
                          aria-label="Toggle snippet"
                        >
                          {expanded ? "▾" : "▸"}
                        </button>
                      </td>
                      <td>{r.rule_id ?? "-"}</td>
                      <td>
                        {r.message ? (
                          r.message
                        ) : isNoop ? (
                          <span className="pill noop">{t("rules.noopBadge")}</span>
                        ) : (
                          "-"
                        )}
                      </td>
                      <td>
                        {canWrite && (
                          <button
                            className="btn"
                            disabled={!r.rule_id}
                            onClick={() =>
                              api
                                .toggleRule(r.id, !r.enabled)
                                .then(() => {
                                  openRules(files.find((f) => f.id === rulesOf.fileId)!);
                                  refreshFiles();
                                })
                                .catch((e) => toast.error(String(e)))
                            }
                          >
                            {r.enabled ? t("common.disable") : t("common.enable")}
                          </button>
                        )}
                      </td>
                    </tr>
                    {expanded && (
                      <tr>
                        <td colSpan={4}>
                          <pre className="rule-snippet">{r.raw_snippet}</pre>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
              {rulesOf.rows.length === 0 && (
                <tr>
                  <td colSpan={4} className="muted">
                    {t("rules.noParsedRules")}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Modal>
      )}

      {historyOf && (
        <Modal title={t("rules.historyTitle", { filename: historyOf.filename })} onClose={() => setHistoryOf(null)}>
          {historyOf.versions.length === 0 ? (
            <p className="muted">{t("rules.historyEmpty")}</p>
          ) : (
            <p className="muted">{t("rules.historyIntro")}</p>
          )}
          {historyOf.versions.map((v) => {
            const open = previewVersionId === v.id;
            return (
              <div className="version-row" key={v.id}>
                <div className="version-summary">
                  <button
                    className="rule-snippet-toggle"
                    onClick={() => setPreviewVersionId(open ? null : v.id)}
                    aria-label={t("rules.versionPreview")}
                  >
                    {open ? "▾" : "▸"}
                  </button>
                  <div>
                    <strong>{new Date(v.created_at).toLocaleString()}</strong>{" "}
                    <span className="muted">· {v.size_bytes} bytes</span>
                  </div>
                  {canWrite && (
                    <button className="btn" style={{ marginLeft: "auto" }} onClick={() => doRevert(v)}>
                      {t("rules.revert")}
                    </button>
                  )}
                </div>
                {open && <pre className="rule-snippet">{v.content}</pre>}
              </div>
            );
          })}
        </Modal>
      )}

      {saveConfirm && (
        <Modal title={t("rules.saveCheckTitle")} onClose={() => setSaveConfirm(null)}>
          <p className="muted">{t("rules.saveCheckDescription")}</p>
          <div className="lint-warnings" style={{ marginTop: 10 }}>
            <ul>
              {saveConfirm.map((w, i) => (
                <li key={i}>
                  {warningMessage(w, t)}
                  {w.fix && (
                    <button className="btn lint-fix-btn" onClick={() => activateFix(w.fix!)}>
                      {fixButtonLabel(w.fix, t)}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
            <button className="btn btn-primary" onClick={performSave}>
              {t("rules.saveAnyway")}
            </button>
            <button className="btn" onClick={() => setSaveConfirm(null)}>
              {t("rules.backToEditing")}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
