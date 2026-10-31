import { NavLink } from "react-router-dom";

export function Nav() {
  return (
    <nav className="nav">
      <h1>Sentinel WAF</h1>
      <NavLink to="/" className={({ isActive }) => (isActive ? "active" : "")} end>
        Dashboard
      </NavLink>
      <NavLink to="/logs" className={({ isActive }) => (isActive ? "active" : "")}>
        Logs
      </NavLink>
      <NavLink to="/rules" className={({ isActive }) => (isActive ? "active" : "")}>
        Rules
      </NavLink>
      <NavLink to="/sites" className={({ isActive }) => (isActive ? "active" : "")}>
        Sites
      </NavLink>
      <NavLink to="/settings" className={({ isActive }) => (isActive ? "active" : "")}>
        Settings
      </NavLink>
    </nav>
  );
}
