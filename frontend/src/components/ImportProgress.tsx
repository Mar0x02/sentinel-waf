import { useLanguage } from "../i18n/LanguageContext";
import { ImportRunState } from "../hooks/useStagedImport";

export function ImportProgress({ run, onDismiss }: { run: ImportRunState; onDismiss: () => void }) {
  const { t } = useLanguage();

  return (
    <div className="import-progress">
      <div className="import-progress-track">
        <div
          className={`import-progress-fill ${run.error ? "error" : ""}`}
          style={{ width: `${run.percent}%` }}
        />
      </div>
      <div className="import-progress-row">
        <span className="muted">
          {run.error ? t("rules.importError", { error: run.error }) : t(run.labelKey)}
        </span>
        {run.done && (
          <button className="btn" onClick={onDismiss}>
            {t("rules.dismiss")}
          </button>
        )}
      </div>
      {run.done && !run.error && run.fileNames && run.fileNames.length > 0 && (
        <div className="muted import-progress-files">
          {t("rules.importedFilesSummary", { count: String(run.fileNames.length) })}{" "}
          {run.fileNames.join(", ")}
        </div>
      )}
    </div>
  );
}
