import { useEffect, useState } from "react";
import { api, CatalogEntry, RuleFile, RuleRow, RuleSet } from "../api/client";

function RuleFilesPanel({ ruleSet, onChanged }: { ruleSet: RuleSet; onChanged: () => void }) {
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

  return (
    <div className="card" style={{ marginTop: 8 }}>
      {error && <p>{error}</p>}
      {files
        .filter((f) => f.file_kind !== "asset")
        .map((f) => (
          <div className="rule-file-row" key={f.id}>
            <div>
              <strong>{f.filename}</strong>{" "}
              <span className="muted">
                {f.rule_count} rule(s) · {f.size_bytes} bytes {f.file_kind === "setup" && "· setup file"}
              </span>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn" onClick={() => openRules(f)}>
                View rules
              </button>
              {isCustom && (
                <button className="btn" onClick={() => openEditor(f)}>
                  Edit
                </button>
              )}
              <button className="btn" onClick={() => api.toggleRuleFile(f.id, !f.enabled).then(() => { refresh(); onChanged(); })}>
                {f.enabled ? "Disable" : "Enable"}
              </button>
              {isCustom && (
                <button
                  className="btn"
                  onClick={() => {
                    if (confirm(`Delete ${f.filename}?`)) {
                      api.deleteRuleFile(f.id).then(() => { refresh(); onChanged(); });
                    }
                  }}
                >
                  Delete
                </button>
              )}
            </div>
          </div>
        ))}
      {files.filter((f) => f.file_kind !== "asset").length === 0 && (
        <p className="muted">No rule files in this set.</p>
      )}

      {isCustom && (
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <input placeholder="new-rule.conf" value={newFilename} onChange={(e) => setNewFilename(e.target.value)} />
          <button className="btn" onClick={createFile}>
            + New rule file
          </button>
        </div>
      )}

      {editing && (
        <div className="card">
          <h3>Editing {editing.filename}</h3>
          <textarea
            className="rule-editor"
            value={editing.content}
            onChange={(e) => setEditing({ ...editing, content: e.target.value })}
          />
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button className="btn" onClick={saveEditor}>
              Save
            </button>
            <button className="btn" onClick={() => setEditing(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {rulesOf && (
        <div className="card">
          <h3>Rules in this file</h3>
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Message</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rulesOf.rows.map((r) => (
                <tr key={r.id}>
                  <td>{r.rule_id ?? "-"}</td>
                  <td>{r.message ?? "-"}</td>
                  <td>
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
                      {r.enabled ? "Disable" : "Enable"}
                    </button>
                  </td>
                </tr>
              ))}
              {rulesOf.rows.length === 0 && (
                <tr>
                  <td colSpan={3} className="muted">
                    No individually-parsed rules found in this file.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <button className="btn" style={{ marginTop: 8 }} onClick={() => setRulesOf(null)}>
            Close
          </button>
        </div>
      )}
    </div>
  );
}

export function RulesPage() {
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
      <h2>Rule Sets</h2>
      {error && <p>{error}</p>}

      <div className="card">
        <h3>Import OWASP CRS (pick a version)</h3>
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
                {imported ? "Imported" : busy ? "Importing..." : "Import"}
              </button>
            </div>
          );
        })}
      </div>

      <div className="card">
        <h3>Import custom rule package from a URL</h3>
        <p className="muted">
          Points at a .tar.gz/.zip (any .conf/.data files inside are picked up) or a single raw .conf file.
        </p>
        <div style={{ display: "flex", gap: 8 }}>
          <input placeholder="Name" value={urlName} onChange={(e) => setUrlName(e.target.value)} />
          <input
            placeholder="https://..."
            style={{ flex: 1 }}
            value={urlUrl}
            onChange={(e) => setUrlUrl(e.target.value)}
          />
          <button className="btn" disabled={busy} onClick={doImportUrl}>
            Import
          </button>
        </div>
      </div>

      <h2>Installed Rule Sets</h2>
      {ruleSets.map((rs) => (
        <div className="card" key={rs.id}>
          <div className="rule-file-row" style={{ borderBottom: "none" }}>
            <div>
              <strong>{rs.name}</strong> {rs.version && <span className="muted">v{rs.version}</span>}{" "}
              <span className="muted">
                · {rs.file_count} file(s) · {rs.rule_count} rule(s) · {rs.source_type}
              </span>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn" onClick={() => setExpanded(expanded === rs.id ? null : rs.id)}>
                {expanded === rs.id ? "Hide files" : "Show files"}
              </button>
              <button className="btn" onClick={() => api.toggleRuleSet(rs.id, !rs.enabled).then(refresh)}>
                {rs.enabled ? "Disable" : "Enable"}
              </button>
              {rs.slug !== "custom" && (
                <button
                  className="btn"
                  onClick={() => {
                    if (confirm(`Delete rule set "${rs.name}"? This removes all its files and rules.`)) {
                      api.deleteRuleSet(rs.id).then(refresh);
                    }
                  }}
                >
                  Delete
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
