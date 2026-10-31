import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useLanguage } from "../i18n/LanguageContext";

export function Nav() {
  const { lang, setLang, t } = useLanguage();
  const { username, logout } = useAuth();

  return (
    <nav className="nav">
      <h1>{t("nav.brand")}</h1>
      <NavLink to="/" className={({ isActive }) => (isActive ? "active" : "")} end>
        {t("nav.dashboard")}
      </NavLink>
      <NavLink to="/logs" className={({ isActive }) => (isActive ? "active" : "")}>
        {t("nav.logs")}
      </NavLink>
      <NavLink to="/rules" className={({ isActive }) => (isActive ? "active" : "")}>
        {t("nav.rules")}
      </NavLink>
      <NavLink to="/sites" className={({ isActive }) => (isActive ? "active" : "")}>
        {t("nav.sites")}
      </NavLink>
      <NavLink to="/error-pages" className={({ isActive }) => (isActive ? "active" : "")}>
        {t("nav.errorPages")}
      </NavLink>
      <NavLink to="/settings" className={({ isActive }) => (isActive ? "active" : "")}>
        {t("nav.settings")}
      </NavLink>

      <div style={{ marginTop: "auto" }}>
        {username && (
          <div className="muted" style={{ padding: "0 12px", fontSize: 12, marginBottom: 8 }}>
            {username}
          </div>
        )}
        <button className="btn" style={{ width: "100%", marginBottom: 10 }} onClick={logout}>
          {t("nav.logout")}
        </button>
        <div className="lang-switch">
          <button className={lang === "en" ? "active" : ""} onClick={() => setLang("en")}>
            EN
          </button>
          <button className={lang === "id" ? "active" : ""} onClick={() => setLang("id")}>
            ID
          </button>
        </div>
      </div>
    </nav>
  );
}
