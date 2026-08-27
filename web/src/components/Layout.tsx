import { NavLink, Outlet } from "react-router-dom";

const NAV = [
  { to: "/", label: "总览", end: true },
  { to: "/fat-loss", label: "减脂分析" },
  { to: "/muscle", label: "增肌训练" },
  { to: "/rhythm", label: "训练节奏" },
  { to: "/movements", label: "动作进步" },
  { to: "/calendar", label: "训练日历" },
];

export default function Layout() {
  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>训记 Dashboard</h1>
        <p className="sub">减脂 · 增肌 · 数据可视化</p>
        <nav>
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
