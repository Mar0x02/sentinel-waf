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
      <form className="login-card" onSubmit={submit}>
        <h1>{t("nav.brand")}</h1>
        <h2>{t("auth.loginTitle")}</h2>
        {error && <p className="login-error">{error}</p>}
        <label>
          {t("auth.username")}
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        </label>
        <label>
          {t("auth.password")}
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        <button className="btn" type="submit" disabled={busy}>
          {t("auth.loginButton")}
        </button>
      </form>
    </div>
  );
}
