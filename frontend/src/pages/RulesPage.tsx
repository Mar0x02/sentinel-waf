import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api, CatalogEntry, RuleSet } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useConfirm } from "../components/ConfirmProvider";
import { ImportProgress } from "../components/ImportProgress";
import { useStagedImport } from "../hooks/useStagedImport";
import { useLanguage } from "../i18n/LanguageContext";

export function RulesPage() {
  const { t } = useLanguage();
  const { canWrite } = useAuth();
  const confirm = useConfirm();
  const [ruleSets, setRuleSets] = useState<RuleSet[]>([]);
  const [catalog, setCatalog] = useState<CatalogEntry[]>([]);
  const [urlName, setUrlName] = useState("");
  const [urlUrl, setUrlUrl] = useState("");
  const catalogImport = useStagedImport();
  const urlImport = useStagedImport();

  function refresh() {
    api.listRuleSets().then(setRuleSets).catch((e) => toast.error(String(e)));
  }

  useEffect(() => {
    refresh();
    api.listCatalog().then(setCatalog).catch((e) => toast.error(String(e)));
  }, []);

  function notifyCarriedOver(ruleSet: RuleSet) {
    if (ruleSet.carried_over_tunables.length > 0) {
      toast.success(
        t("rules.carriedOverTunables", {
          count: ruleSet.carried_over_tunables.length,
          ids: ruleSet.carried_over_tunables.join(", "),
        })
      );
    }
  }

  async function doImportCatalog(id: string) {
    try {
      const ruleSet = await catalogImport.start(
        `catalog:${id}`,
        () => api.importCatalog(id),
        (ruleSetId) => api.listRuleFiles(ruleSetId).then((files) => files.map((f) => f.filename))
      );
      notifyCarriedOver(ruleSet);
      refresh();
    } catch {
      // error already captured in catalogImport.run.error
    }
  }

  async function doImportUrl() {
    if (!urlName.trim() || !urlUrl.trim()) return;
    try {
      const ruleSet = await urlImport.start(
        "url",
        () => api.importUrl(urlName, urlUrl),
        (ruleSetId) => api.listRuleFiles(ruleSetId).then((files) => files.map((f) => f.filename))
      );
      notifyCarriedOver(ruleSet);
      setUrlName("");
      setUrlUrl("");
      refresh();
    } catch {
      // error already captured in urlImport.run.error
    }
  }

  const customSet = ruleSets.find((rs) => rs.slug === "custom");
  const baseTuningSet = ruleSets.find((rs) => rs.slug === "base-tuning");
  const otherSets = ruleSets.filter((rs) => rs.slug !== "custom" && rs.slug !== "base-tuning");

  function ruleSetRow(rs: RuleSet) {
    return (
      <div className="rule-file-row" key={rs.id}>
        <div>
          <strong>{rs.name}</strong> {rs.version && <span className="muted">v{rs.version}</span>}{" "}
          <span className="muted">
            · {t("rules.fileCount", { count: rs.file_count })} · {t("rules.ruleCount", { count: rs.rule_count })} ·{" "}
            {rs.source_type}
          </span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Link className="btn" to={`/rules/${rs.id}`}>
            {t("rules.viewDetail")}
          </Link>
          {canWrite && (
            <button className="btn" onClick={() => api.toggleRuleSet(rs.id, !rs.enabled).then(refresh)}>
              {rs.enabled ? t("common.disable") : t("common.enable")}
            </button>
          )}
          {canWrite && rs.slug !== "custom" && rs.slug !== "base-tuning" && (
            <button
              className="btn btn-danger"
              onClick={async () => {
                if (await confirm(t("rules.deleteSetConfirm", { name: rs.name }))) {
                  api
                    .deleteRuleSet(rs.id)
                    .then(() => {
                      toast.success(t("rules.deleteSetSuccess", { name: rs.name }));
                      refresh();
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
    );
  }

  return (
    <div>
      <h2>{t("rules.title")}</h2>

      {canWrite && (
        <div className="card">
          <h3>{t("rules.importCrsTitle")}</h3>
          {catalog.map((entry) => {
            const imported = ruleSets.some((rs) => rs.source_url === entry.url);
            const key = `catalog:${entry.id}`;
            const thisRun = catalogImport.run?.key === key ? catalogImport.run : null;
            const inFlight = catalogImport.run !== null && !catalogImport.run.done && catalogImport.run.key === key;
            return (
              <div key={entry.id} style={{ borderBottom: "1px solid var(--gridline)", padding: "10px 0" }}>
                <div className="rule-file-row" style={{ borderBottom: "none", padding: 0 }}>
                  <div>
                    <strong>
                      {entry.name} {entry.version}
                    </strong>
                    <div className="muted">{entry.description}</div>
                  </div>
                  <button className="btn btn-primary" disabled={inFlight || imported} onClick={() => doImportCatalog(entry.id)}>
                    {imported ? t("rules.imported") : inFlight ? t("rules.importing") : t("rules.import")}
                  </button>
                </div>
                {thisRun && <ImportProgress run={thisRun} onDismiss={catalogImport.dismiss} />}
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
            <button className="btn btn-primary" disabled={urlImport.run !== null && !urlImport.run.done} onClick={doImportUrl}>
              {t("rules.import")}
            </button>
          </div>
          {urlImport.run && <ImportProgress run={urlImport.run} onDismiss={urlImport.dismiss} />}
        </div>
      )}

      <h2>{t("rules.installedTitle")}</h2>
      {otherSets.length > 0 && <div className="card">{otherSets.map(ruleSetRow)}</div>}
      {otherSets.length === 0 && <p className="muted">{t("rules.noRuleFiles")}</p>}

      {baseTuningSet && (
        <>
          <h2>{t("rules.baseTuningTitle")}</h2>
          <p className="muted" style={{ marginTop: -8 }}>
            {t("rules.baseTuningDesc")}
          </p>
          <div className="card">{ruleSetRow(baseTuningSet)}</div>
        </>
      )}

      {customSet && (
        <>
          <h2>{t("rules.customTitle")}</h2>
          <div className="card">{ruleSetRow(customSet)}</div>
        </>
      )}
    </div>
  );
}
