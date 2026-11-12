import { AlertTriangle, Archive, Ban, Bug, Github, Globe, LayoutDashboard, Languages, LogOut, ScrollText, Settings, ShieldCheck, Users } from "lucide-react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useLanguage } from "../i18n/LanguageContext";

const navItems = [
  { to: "/", key: "nav.dashboard", icon: LayoutDashboard, end: true },
  { to: "/rules", key: "nav.rules", icon: ShieldCheck, end: false },
  { to: "/sites", key: "nav.sites", icon: Globe, end: false },
  { to: "/anti-bot", key: "nav.antiBot", icon: Bug, end: false },
  { to: "/access-control", key: "nav.accessControl", icon: Ban, end: false },
  { to: "/error-pages", key: "nav.errorPages", icon: AlertTriangle, end: false },
  { to: "/settings", key: "nav.settings", icon: Settings, end: false },
] as const;

export function Nav() {
  const { lang, setLang, t } = useLanguage();
  const { username, isAdmin, logout } = useAuth();

  const initials = username ? username.slice(0, 2).toUpperCase() : "?";

  return (
    <nav className="nav">
      <h1 className="nav-brand">
        <ShieldCheck size={20} strokeWidth={2.25} />
        <span>{t("nav.brand")}</span>
      </h1>

      <div className="nav-links">
        <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
          <LayoutDashboard size={17} strokeWidth={2} />
          <span>{t("nav.dashboard")}</span>
        </NavLink>

        <div className="nav-group">
          <span className="nav-group-label">{t("nav.logs")}</span>
          <NavLink to="/logs" end className={({ isActive }) => (isActive ? "active" : "")}>
            <span className="nav-live-dot" aria-hidden="true" />
            <ScrollText size={17} strokeWidth={2} />
            <span>{t("nav.liveLog")}</span>
          </NavLink>
          <NavLink to="/logs/archive" className={({ isActive }) => (isActive ? "active" : "")}>
            <Archive size={17} strokeWidth={2} />
            <span>{t("nav.logArchive")}</span>
          </NavLink>
        </div>

        {navItems.map(({ to, key, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} className={({ isActive }) => (isActive ? "active" : "")}>
            <Icon size={17} strokeWidth={2} />
            <span>{t(key)}</span>
          </NavLink>
        ))}
        {isAdmin && (
          <NavLink to="/team" className={({ isActive }) => (isActive ? "active" : "")}>
            <Users size={17} strokeWidth={2} />
            <span>{t("nav.team")}</span>
          </NavLink>
        )}
      </div>

      <div className="nav-footer">
        <div className="lang-switch">
          <Languages size={14} className="lang-switch-icon" />
          <button className={lang === "en" ? "active" : ""} onClick={() => setLang("en")}>
            EN
          </button>
          <button className={lang === "id" ? "active" : ""} onClick={() => setLang("id")}>
            ID
          </button>
        </div>

        {username && (
          <div className="nav-user">
            <div className="nav-avatar">{initials}</div>
            <span className="nav-username" title={username}>
              {username}
            </span>
            <button className="nav-logout" onClick={logout} aria-label={t("nav.logout")} title={t("nav.logout")}>
              <LogOut size={16} strokeWidth={2} />
            </button>
          </div>
        )}

        <a
          className="nav-credit"
          href="https://github.com/Mar0x02/sentinel-waf"
          target="_blank"
          rel="noreferrer"
          title="Mar0x02/sentinel-waf"
        >
          <Github size={13} strokeWidth={2} />
          <span>Mar0x02/sentinel-waf</span>
        </a>
      </div>
    </nav>
  );
}
