import { ChangePasswordForm } from "../components/ChangePasswordForm";
import { useAuth } from "../auth/AuthContext";
import { useLanguage } from "../i18n/LanguageContext";

export function ForcedChangePasswordPage() {
  const { t } = useLanguage();
  const { onPasswordChanged } = useAuth();

  return (
    <div className="login-shell">
      <div className="login-card">
        <h1>{t("nav.brand")}</h1>
        <h2>{t("auth.forcedChangeTitle")}</h2>
        <p className="muted">{t("auth.forcedChangeDesc")}</p>
        <ChangePasswordForm onSuccess={onPasswordChanged} />
      </div>
    </div>
  );
}
