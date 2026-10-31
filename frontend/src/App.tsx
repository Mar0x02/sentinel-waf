import { Route, Routes } from "react-router-dom";
import { Nav } from "./components/Nav";
import { DashboardPage } from "./pages/DashboardPage";
import { LogsPage } from "./pages/LogsPage";
import { RulesPage } from "./pages/RulesPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SitesPage } from "./pages/SitesPage";

export function App() {
  return (
    <div className="app-shell">
      <Nav />
      <div className="main">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/logs" element={<LogsPage />} />
          <Route path="/rules" element={<RulesPage />} />
          <Route path="/sites" element={<SitesPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </div>
    </div>
  );
}
