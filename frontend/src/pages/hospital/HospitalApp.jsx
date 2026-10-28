import { Link, Navigate, Route, Routes } from "react-router";
import { HospitalProvider } from "./HospitalContext";
import HospitalLayout from "./HospitalLayout";
import Overview from "./pages/Overview";
import Incidents from "./pages/Incidents";
import IncidentDetail from "./pages/IncidentDetail";
import Operations from "./pages/Operations";
import Health from "./pages/Health";
import Reports from "./pages/Reports";
import "./HospitalDashboard.css";

// Mount once under your existing BrowserRouter at /hospital/*.
export default function HospitalApp({ embedded = false }) {
  return (
    <HospitalProvider>
      <Routes>
        <Route element={<HospitalLayout embedded={embedded} />}>
          <Route index element={<Overview />} />
          <Route
            path="overview"
            element={<Navigate to="/hospital" replace />}
          />
          <Route path="incidents" element={<Incidents />} />
          <Route path="incidents/:incidentId" element={<IncidentDetail />} />
          <Route path="operations" element={<Operations />} />
          <Route path="health" element={<Health />} />
          <Route path="reports" element={<Reports />} />
          {/* Keep links from the first UI package working. */}
          <Route
            path="alerts"
            element={<Navigate to="/hospital/incidents" replace />}
          />
          <Route
            path="map"
            element={<Navigate to="/hospital/health" replace />}
          />
          <Route
            path="history"
            element={<Navigate to="/hospital/operations" replace />}
          />
          <Route
            path="settings"
            element={<Navigate to="/hospital/operations" replace />}
          />
          <Route
            path="*"
            element={
              <section className="hd-panel hd-empty">
                <h2>Page not found</h2>
                <Link to="/hospital" className="hd-button hd-button-primary">
                  Back to overview
                </Link>
              </section>
            }
          />
        </Route>
      </Routes>
    </HospitalProvider>
  );
}
