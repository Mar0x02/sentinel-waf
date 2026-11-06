import { Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { LoadingScreen } from "./components/LoadingShield";
import { Nav } from "./components/Nav";
import { AccessControlPage } from "./pages/AccessControlPage";
import { AntiBotPage } from "./pages/AntiBotPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ErrorPagesPage } from "./pages/ErrorPagesPage";
import { ForcedChangePasswordPage } from "./pages/ForcedChangePasswordPage";
import { LoginPage } from "./pages/LoginPage";
import { LogsPage } from "./pages/LogsPage";
import { RuleSetDetailPage } from "./pages/RuleSetDetailPage";
import { RulesPage } from "./pages/RulesPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SitesPage } from "./pages/SitesPage";
import { TeamPage } from "./pages/TeamPage";

export function App() {
  const { loading, isAuthenticated, mustChangePassword, isAdmin } = useAuth();

  if (loading) {
    return <LoadingScreen />;
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
          <Route path="/access-control" element={<AccessControlPage />} />
          <Route path="/rules" element={<RulesPage />} />
          <Route path="/rules/:ruleSetId" element={<RuleSetDetailPage />} />
          <Route path="/sites" element={<SitesPage />} />
          <Route path="/anti-bot" element={<AntiBotPage />} />
          <Route path="/error-pages" element={<ErrorPagesPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          {isAdmin && <Route path="/team" element={<TeamPage />} />}
        </Routes>
      </div>
    </div>
  );
}
