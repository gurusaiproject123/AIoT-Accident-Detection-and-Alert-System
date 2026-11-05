import { useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import Login from "./pages/auth/Login";
import RequireRole from "./pages/auth/RequireRole";
import { homeForProfile } from "./pages/auth/accountRules";
import { useAuth } from "./pages/auth/useAuth";
import "./App.css";

const pages = [
  { path: "/hospital", role: "hospital_staff", title: "Hospital Dashboard" },
  { path: "/superuser", role: "superuser", title: "Superuser Dashboard" },
  { path: "/vehicle", role: "car_owner", title: "Vehicle Controls" },
];

function Workspace({ title }) {
  const { profile, signOut } = useAuth();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function handleSignOut() {
    setPending(true);
    setError("");
    try {
      await signOut();
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <h2>AI GURUS</h2>
        <p>Accident Detection System</p>
        <button type="button" onClick={handleSignOut} disabled={pending}>
          {pending ? "Signing out…" : "Sign out"}
        </button>
        {error && <p role="alert">{error}</p>}
      </aside>
      <main className="main-content">
        <section className="page-panel">
          <h1>{title}</h1>
          <p>Signed in as {profile.name || profile.role}.</p>
          <p>Your account is verified. This branch contains the sign-in page and role routing; dashboard content is added from the corresponding frontend branch.</p>
        </section>
      </main>
    </div>
  );
}

function Home() {
  const { profile, loading } = useAuth();
  if (loading) return <p role="status">Verifying account access…</p>;
  return <Navigate to={homeForProfile(profile)} replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        {pages.map(({ path, role, title }) => (
          <Route key={path} path={path + "/*"} element={
            <RequireRole roles={[role]}>
              <Workspace title={title} />
            </RequireRole>
          } />
        ))}
        <Route path="*" element={<Home />} />
      </Routes>
    </BrowserRouter>
  );
}
