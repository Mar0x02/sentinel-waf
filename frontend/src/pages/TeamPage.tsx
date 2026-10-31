import { useEffect, useState } from "react";
import { Role, TeamUser, usersApi } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useLanguage } from "../i18n/LanguageContext";

const emptyForm = { username: "", password: "", role: "viewer" as Role };

export function TeamPage() {
  const { t } = useLanguage();
  const { username: myUsername } = useAuth();
  const [users, setUsers] = useState<TeamUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);

  function refresh() {
    usersApi.list().then(setUsers).catch((e) => setError(String(e)));
  }

  useEffect(refresh, []);

  async function submit() {
    if (!form.username.trim() || form.password.length < 8) return;
    try {
      await usersApi.create(form.username, form.password, form.role);
      setForm(emptyForm);
      refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  async function changeRole(user: TeamUser, role: Role) {
    try {
      await usersApi.updateRole(user.id, role);
      refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  async function resetPassword(user: TeamUser) {
    if (!confirm(t("team.resetConfirm", { username: user.username }))) return;
    try {
      const result = await usersApi.resetPassword(user.id);
      alert(t("team.resetSuccess", { username: result.username, password: result.new_password }));
      refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  async function deleteUser(user: TeamUser) {
    if (user.username === myUsername) {
      alert(t("team.cantDeleteSelf"));
      return;
    }
    if (!confirm(t("team.deleteConfirm", { username: user.username }))) return;
    try {
      await usersApi.delete(user.id);
      refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <div>
      <h2>{t("team.title")}</h2>
      <p className="muted">{t("team.description")}</p>

      {error && <p>{error}</p>}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>{t("team.username")}</th>
              <th>{t("team.role")}</th>
              <th>{t("team.created")}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>
                  {u.username} {u.username === myUsername && <span className="muted">{t("team.you")}</span>}
                  {u.must_change_password && (
                    <div className="muted" style={{ fontSize: 11 }}>
                      {t("team.mustChangePassword")}
                    </div>
                  )}
                </td>
                <td>
                  <select value={u.role} onChange={(e) => changeRole(u, e.target.value as Role)}>
                    <option value="admin">{t("role.admin")}</option>
                    <option value="operator">{t("role.operator")}</option>
                    <option value="viewer">{t("role.viewer")}</option>
                  </select>
                </td>
                <td>{new Date(u.created_at).toLocaleDateString()}</td>
                <td style={{ display: "flex", gap: 8 }}>
                  <button className="btn" onClick={() => resetPassword(u)}>
                    {t("team.resetPassword")}
                  </button>
                  <button className="btn" onClick={() => deleteUser(u)}>
                    {t("common.delete")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>{t("team.addUser")}</h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input
            placeholder={t("team.usernamePlaceholder")}
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
          />
          <input
            type="password"
            placeholder={t("team.passwordPlaceholder")}
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
            <option value="admin">{t("role.admin")}</option>
            <option value="operator">{t("role.operator")}</option>
            <option value="viewer">{t("role.viewer")}</option>
          </select>
          <button className="btn" onClick={submit}>
            {t("team.addUser")}
          </button>
        </div>
      </div>
    </div>
  );
}
