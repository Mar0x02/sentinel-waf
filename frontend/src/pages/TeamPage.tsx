import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Role, TeamUser, usersApi } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useConfirm } from "../components/ConfirmProvider";
import { useLanguage } from "../i18n/LanguageContext";

const emptyForm = { username: "", password: "", role: "viewer" as Role };

export function TeamPage() {
  const { t } = useLanguage();
  const { username: myUsername } = useAuth();
  const confirm = useConfirm();
  const [users, setUsers] = useState<TeamUser[]>([]);
  const [form, setForm] = useState(emptyForm);

  function refresh() {
    usersApi.list().then(setUsers).catch((e) => toast.error(String(e)));
  }

  useEffect(refresh, []);

  async function submit() {
    if (!form.username.trim() || form.password.length < 8) return;
    try {
      await usersApi.create(form.username, form.password, form.role);
      toast.success(t("team.addUserSuccess", { username: form.username }));
      setForm(emptyForm);
      refresh();
    } catch (e) {
      toast.error(String(e));
    }
  }

  async function changeRole(user: TeamUser, role: Role) {
    try {
      await usersApi.updateRole(user.id, role);
      toast.success(t("team.roleChangeSuccess", { username: user.username }));
      refresh();
    } catch (e) {
      toast.error(String(e));
    }
  }

  async function resetPassword(user: TeamUser) {
    if (!(await confirm(t("team.resetConfirm", { username: user.username })))) return;
    try {
      const result = await usersApi.resetPassword(user.id);
      // Deliberately not auto-dismissed (duration: Infinity) and with the
      // closeButton the Toaster provides globally - this is a one-time
      // credential, same as the first-boot admin password. A toast that
      // vanishes on its own timer before it's copied would just mean
      // another reset.
      toast.success(t("team.resetSuccess", { username: result.username, password: result.new_password }), {
        duration: Infinity,
      });
      refresh();
    } catch (e) {
      toast.error(String(e));
    }
  }

  async function deleteUser(user: TeamUser) {
    if (user.username === myUsername) {
      toast.error(t("team.cantDeleteSelf"));
      return;
    }
    if (!(await confirm(t("team.deleteConfirm", { username: user.username })))) return;
    try {
      await usersApi.delete(user.id);
      toast.success(t("team.deleteSuccess", { username: user.username }));
      refresh();
    } catch (e) {
      toast.error(String(e));
    }
  }

  return (
    <div>
      <h2>{t("team.title")}</h2>
      <p className="muted">{t("team.description")}</p>

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
                  <button className="btn btn-danger" onClick={() => deleteUser(u)}>
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
          <button className="btn btn-primary" onClick={submit}>
            {t("team.addUser")}
          </button>
        </div>
      </div>
    </div>
  );
}
