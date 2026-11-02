import { createContext, ReactNode, useCallback, useContext, useState } from "react";
import { useLanguage } from "../i18n/LanguageContext";

type ConfirmFn = (message: string) => Promise<boolean>;

interface PendingConfirm {
  message: string;
  resolve: (ok: boolean) => void;
}

const ConfirmContext = createContext<ConfirmFn | null>(null);

// Replaces the native window.confirm() used across the app - same
// call-site shape (await it, branch on the boolean) but styled to match
// the dashboard's own dark/cyan theme instead of the browser's default
// dialog. See styles.css's .confirm-card rules.
export function ConfirmProvider({ children }: { children: ReactNode }) {
  const { t } = useLanguage();
  const [pending, setPending] = useState<PendingConfirm | null>(null);

  const confirm = useCallback<ConfirmFn>((message) => {
    return new Promise<boolean>((resolve) => {
      setPending({ message, resolve });
    });
  }, []);

  function settle(result: boolean) {
    pending?.resolve(result);
    setPending(null);
  }

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {pending && (
        <div className="modal-overlay" onClick={() => settle(false)}>
          <div className="modal-card confirm-card" onClick={(e) => e.stopPropagation()}>
            <p>{pending.message}</p>
            <div className="confirm-actions">
              <button className="btn" onClick={() => settle(false)}>
                {t("common.cancel")}
              </button>
              <button className="btn btn-danger" autoFocus onClick={() => settle(true)}>
                {t("common.confirm")}
              </button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  );
}

export function useConfirm(): ConfirmFn {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error("useConfirm must be used within ConfirmProvider");
  return ctx;
}
