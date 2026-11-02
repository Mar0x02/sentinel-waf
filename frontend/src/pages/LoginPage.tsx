import { KeyRound, Loader2, ShieldCheck, User } from "lucide-react";
import { FormEvent, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { useLanguage } from "../i18n/LanguageContext";

export function LoginPage() {
  const { t } = useLanguage();
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
    } catch {
      setError(t("auth.loginError"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-shell">
      <div className="login-glow" />
      <form className="login-card" onSubmit={submit}>
        <div className="login-brand">
          <div className="login-brand-icon">
            <ShieldCheck size={26} strokeWidth={2} />
          </div>
          <h1>{t("nav.brand")}</h1>
          <p className="login-tagline">{t("auth.loginTitle")}</p>
        </div>

        {error && <p className="login-error">{error}</p>}

        <label>
          {t("auth.username")}
          <div className="login-input-wrap">
            <User size={15} />
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus autoComplete="username" />
          </div>
        </label>
        <label>
          {t("auth.password")}
          <div className="login-input-wrap">
            <KeyRound size={15} />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>
        </label>
        <button className="btn btn-primary login-submit" type="submit" disabled={busy}>
          {busy && <Loader2 size={15} className="login-spinner" />}
          {t("auth.loginButton")}
        </button>
      </form>
    </div>
  );
}
