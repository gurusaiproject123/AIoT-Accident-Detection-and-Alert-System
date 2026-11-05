import { useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";

import Login from "./pages/auth/Login";
import RequireRole from "./pages/auth/RequireRole";
import { homeForProfile } from "./pages/auth/accountRules";
import { useAuth } from "./pages/auth/useAuth";
import HospitalDashboard from "./pages/hospital/HospitalDashboard";
import SuperuserDashboard from "./pages/superuser/SuperuserDashboard";

import "./App.css";

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
      setError(err instanceof Error ? err.message : "Could not sign out. Please try again.");
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
          <p>Your account is verified. This dashboard is still being integrated.</p>
        </section>
      </main>
    </div>
  );
}

function Home() {
  const { profile, loading } = useAuth();

  if (loading) {
    return <p role="status">Verifying account access…</p>;
  }

  return <Navigate to={homeForProfile(profile)} replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />

        <Route
          path="/hospital/*"
          element={<HospitalDashboard />}
        />

        <Route
          path="/superuser/*"
          element={
            <RequireRole roles={["superuser"]}>
              <SuperuserDashboard />
            </RequireRole>
          }
        />

        <Route
          path="/vehicle/*"
          element={
            <RequireRole roles={["car_owner"]}>
              <Workspace title="Vehicle Controls" />
            </RequireRole>
          }
        />

        <Route path="*" element={<Home />} />
      </Routes>
    </BrowserRouter>
  );
}