import {
  BrowserRouter,
  Navigate,
  NavLink,
  Route,
  Routes,
} from "react-router";
import Login from "./pages/auth/Login";
import "./App.css";

const pages = [
  {
    path: "/hospital",
    title: "Hospital Dashboard",
    description:
      "Hospital alerts, incident locations and response history will appear here.",
  },
  {
    path: "/superuser",
    title: "Superuser Dashboard",
    description:
      "System incidents, hospitals, users and device monitoring will appear here.",
  },
  {
    path: "/vehicle",
    title: "Vehicle Controls",
    description:
      "Cellphone driving controls and ESP32 connection status will appear here.",
  },
  {
    path: "/login",
    title: "Login",
    description:
      "Hospital staff and administrators will sign in here.",
  },
];

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/*" element={<DashboardPreview />} />
      </Routes>
    </BrowserRouter>
  );
}

function DashboardPreview() {
  return (
      <div className="app-layout">
        <aside className="sidebar">
          <h2>AI GURUS</h2>
          <p>Accident Detection System</p>

          <nav aria-label="Main navigation">
            {pages.map((page) => (
              <NavLink
                key={page.path}
                to={page.path}
                className={({ isActive }) =>
                  isActive ? "nav-link active" : "nav-link"
                }
              >
                {page.title}
              </NavLink>
            ))}
          </nav>
        </aside>

        <main className="main-content">
          <header>
            <h1>AIoT Accident Detection and Alert System</h1>
            <p className="preview-notice">
              Development preview — authentication, backend and
              vehicle connections are not configured yet.
            </p>
          </header>

          <Routes>
            <Route
              path="/"
              element={<Navigate to="/login" replace />}
            />

            {pages.filter((page) => page.path !== "/login").map((page) => (
              <Route
                key={page.path}
                path={page.path}
                element={
                  <section className="page-panel">
                    <h2>{page.title}</h2>
                    <p>{page.description}</p>
                  </section>
                }
              />
            ))}

            <Route
              path="*"
              element={
                <section className="page-panel">
                  <h2>Page not found</h2>
                  <p>Select a page from the navigation.</p>
                </section>
              }
            />
          </Routes>
        </main>
      </div>
  );
}
