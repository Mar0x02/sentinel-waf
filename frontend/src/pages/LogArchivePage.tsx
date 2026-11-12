import { Download, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ArchiveFile, ArchiveDate, logArchiveApi } from "../api/client";
import { useConfirm } from "../components/ConfirmProvider";
import { useLanguage } from "../i18n/LanguageContext";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i++;
  }
  return `${value.toFixed(1)} ${units[i]}`;
}

export function LogArchivePage() {
  const { t } = useLanguage();
  const confirm = useConfirm();
  const [dates, setDates] = useState<ArchiveDate[]>([]);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [files, setFiles] = useState<ArchiveFile[]>([]);

  function reloadDates() {
    logArchiveApi
      .listDates()
      .then(setDates)
      .catch((e) => toast.error(t("archive.loadDatesError", { error: String(e) })));
  }

  useEffect(() => {
    reloadDates();
  }, []);

  useEffect(() => {
    if (!selectedDate) {
      setFiles([]);
      return;
    }
    logArchiveApi
      .listFiles(selectedDate)
      .then(setFiles)
      .catch((e) => toast.error(t("archive.loadFilesError", { date: selectedDate, error: String(e) })));
  }, [selectedDate]);

  async function handleDownload(file: ArchiveFile, format: "gz" | "log") {
    if (!selectedDate) return;
    try {
      if (format === "gz") await logArchiveApi.downloadGz(selectedDate, file.filename);
      else await logArchiveApi.downloadLog(selectedDate, file.filename);
    } catch (e) {
      toast.error(t("archive.downloadError", { filename: file.filename, error: String(e) }));
    }
  }

  async function handleDelete(file: ArchiveFile) {
    if (!selectedDate) return;
    if (!(await confirm(t("archive.deleteConfirm", { filename: file.filename })))) return;
    try {
      await logArchiveApi.delete(selectedDate, file.filename);
      setFiles((prev) => prev.filter((f) => f.filename !== file.filename));
      toast.success(t("archive.deleteSuccess", { filename: file.filename }));
      reloadDates();
    } catch (e) {
      toast.error(t("archive.deleteError", { filename: file.filename, error: String(e) }));
    }
  }

  return (
    <div>
      <h2>{t("archive.title")}</h2>
      <div className="archive-layout">
        <div className="card archive-date-list">
          <h3>{t("archive.datesTitle")}</h3>
          {dates.length === 0 ? (
            <p className="muted">{t("archive.noDates")}</p>
          ) : (
            dates.map((d) => (
              <button
                key={d.date}
                className={`archive-date-item ${selectedDate === d.date ? "active" : ""}`}
                onClick={() => setSelectedDate(d.date)}
              >
                <span>{d.date}</span>
                <span className="muted">{t("archive.fileCount", { count: d.file_count })}</span>
              </button>
            ))
          )}
        </div>

        <div className="card archive-files">
          {!selectedDate ? (
            <p className="muted">{t("archive.selectDate")}</p>
          ) : (
            <>
              <h3>{t("archive.filesTitle", { date: selectedDate })}</h3>
              <table>
                <thead>
                  <tr>
                    <th>{t("archive.timeRange")}</th>
                    <th>{t("archive.size")}</th>
                    <th>{t("archive.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {files.map((f) => (
                    <tr key={f.filename}>
                      <td>
                        {f.start_time} - {f.end_time}
                      </td>
                      <td>{formatBytes(f.size_bytes)}</td>
                      <td className="archive-actions">
                        <button className="btn" onClick={() => handleDownload(f, "gz")} title={t("archive.downloadGz")}>
                          <Download size={14} /> .gz
                        </button>
                        <button className="btn" onClick={() => handleDownload(f, "log")} title={t("archive.downloadLog")}>
                          <Download size={14} /> .log
                        </button>
                        <button className="btn btn-danger" onClick={() => handleDelete(f)} title={t("archive.delete")}>
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                  {files.length === 0 && (
                    <tr>
                      <td colSpan={3} className="muted">
                        {t("archive.noFiles")}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
