import { Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { Nav } from "./components/Nav";
import { useLanguage } from "./i18n/LanguageContext";
import { DashboardPage } from "./pages/DashboardPage";
import { ErrorPagesPage } from "./pages/ErrorPagesPage";
import { ForcedChangePasswordPage } from "./pages/ForcedChangePasswordPage";
import { LoginPage } from "./pages/LoginPage";
import { LogsPage } from "./pages/LogsPage";
import { RulesPage } from "./pages/RulesPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SitesPage } from "./pages/SitesPage";

export function App() {
  const { t } = useLanguage();
  const { loading, isAuthenticated, mustChangePassword } = useAuth();

  if (loading) {
    return (
      <div className="login-shell">
        <p>{t("common.loading")}</p>
      </div>
    );
  }

  if (!isAuthenticated) return <LoginPage />;
  if (mustChangePassword) return <ForcedChangePasswordPage />;

  return (
    <div className="app-shell">
      <Nav />
      <div className="main">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/logs" element={<LogsPage />} />
          <Route path="/rules" element={<RulesPage />} />
          <Route path="/sites" element={<SitesPage />} />
          <Route path="/error-pages" element={<ErrorPagesPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </div>
    </div>
  );
}
