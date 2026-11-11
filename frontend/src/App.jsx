import VehicleDashboard from "./pages/vehicle/VehicleDashboard";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";

import Login from "./pages/auth/Login";
import RequireRole from "./pages/auth/RequireRole";
import { homeForProfile } from "./pages/auth/accountRules";
import { useAuth } from "./pages/auth/useAuth";
import HospitalDashboard from "./pages/hospital/HospitalDashboard";
import SuperuserDashboard from "./pages/superuser/SuperuserDashboard";

import "./App.css";

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
              <VehicleDashboard />
            </RequireRole>
          }
        />

        <Route path="*" element={<Home />} />
      </Routes>
    </BrowserRouter>
  );
}