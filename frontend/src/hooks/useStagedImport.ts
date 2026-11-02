import { useRef, useState } from "react";

// The backend import endpoint is a single blocking call (fetch -> extract ->
// parse -> write) with no real incremental progress to report - there's no
// SSE/websocket channel for it. This simulates plausible stages on a timer
// purely for perceived feedback, then snaps to the real result (file count,
// file names) the moment the actual request resolves. It's honest in that
// the percentage before completion is never claimed to reflect real bytes
// transferred - only the stage label changes.
const STAGES = [
  { percent: 20, labelKey: "rules.importStageFetching" },
  { percent: 50, labelKey: "rules.importStageExtracting" },
  { percent: 78, labelKey: "rules.importStageParsing" },
  { percent: 92, labelKey: "rules.importStageWriting" },
] as const;

export interface ImportRunState {
  key: string;
  percent: number;
  labelKey: string;
  done: boolean;
  error: string | null;
  fileNames: string[] | null;
}

export function useStagedImport() {
  const [run, setRun] = useState<ImportRunState | null>(null);
  const timersRef = useRef<number[]>([]);

  function clearTimers() {
    timersRef.current.forEach((t) => window.clearTimeout(t));
    timersRef.current = [];
  }

  async function start<T extends { id: number }>(
    key: string,
    task: () => Promise<T>,
    fetchFileNames: (id: number) => Promise<string[]>
  ) {
    clearTimers();
    setRun({ key, percent: 6, labelKey: "rules.importStageFetching", done: false, error: null, fileNames: null });

    STAGES.forEach((stage, i) => {
      const t = window.setTimeout(() => {
        setRun((prev) => (prev && prev.key === key && !prev.done ? { ...prev, ...stage } : prev));
      }, 400 * (i + 1));
      timersRef.current.push(t);
    });

    try {
      const result = await task();
      clearTimers();
      let fileNames: string[] = [];
      try {
        fileNames = await fetchFileNames(result.id);
      } catch {
        // best-effort only - the import itself already succeeded
      }
      setRun({ key, percent: 100, labelKey: "rules.importStageDone", done: true, error: null, fileNames });
      return result;
    } catch (e) {
      clearTimers();
      setRun({ key, percent: 100, labelKey: "rules.importStageDone", done: true, error: String(e), fileNames: null });
      throw e;
    }
  }

  function dismiss() {
    clearTimers();
    setRun(null);
  }

  return { run, start, dismiss };
}
