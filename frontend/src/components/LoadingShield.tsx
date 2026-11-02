import { ShieldCheck } from "lucide-react";
import { useLanguage } from "../i18n/LanguageContext";

export function LoadingShield({ size = 40 }: { size?: number }) {
  return (
    <div className="loading-shield" style={{ width: size, height: size }}>
      <ShieldCheck size={size} strokeWidth={1.75} className="loading-shield-base" />
      <ShieldCheck size={size} strokeWidth={1.75} className="loading-shield-fill" />
    </div>
  );
}

export function LoadingScreen() {
  const { t } = useLanguage();
  return (
    <div className="login-shell">
      <div className="loading-screen">
        <LoadingShield size={44} />
        <p className="muted">{t("common.loading")}</p>
      </div>
    </div>
  );
}

// Same animated shield, sized down for loading states inline within a
// normal page's content area (not a full-viewport screen) - e.g. a
// rule-set detail page waiting on its first fetch.
export function LoadingInline() {
  const { t } = useLanguage();
  return (
    <div className="loading-inline">
      <LoadingShield size={30} />
      <p className="muted">{t("common.loading")}</p>
    </div>
  );
}
