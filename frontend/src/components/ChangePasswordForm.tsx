import { FormEvent, useState } from "react";
import { authApi } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";

export function ChangePasswordForm({ onSuccess }: { onSuccess: () => void }) {
  const { t } = useLanguage();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setError(t("auth.passwordMismatch"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await authApi.changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      onSuccess();
    } catch (e) {
      setError(t("auth.changeError", { error: String(e) }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 8, maxWidth: 360 }}>
      {error && <p>{error}</p>}
      <input
        type="password"
        placeholder={t("auth.currentPassword")}
        value={currentPassword}
        onChange={(e) => setCurrentPassword(e.target.value)}
      />
      <input
        type="password"
        placeholder={t("auth.newPassword")}
        value={newPassword}
        onChange={(e) => setNewPassword(e.target.value)}
      />
      <input
        type="password"
        placeholder={t("auth.confirmPassword")}
        value={confirmPassword}
        onChange={(e) => setConfirmPassword(e.target.value)}
      />
      <button className="btn" type="submit" disabled={busy}>
        {t("auth.changePassword")}
      </button>
    </form>
  );
}
