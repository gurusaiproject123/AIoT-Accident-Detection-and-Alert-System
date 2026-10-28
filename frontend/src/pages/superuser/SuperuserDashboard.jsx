import SuperuserApp from "./SuperuserApp";
import "./SuperuserDashboard.css";

/**
 * Entry point used by App.jsx:
 *
 *   import SuperuserDashboard from "./pages/superuser/SuperuserDashboard";
 *   <Route path="/superuser/*" element={<SuperuserDashboard />} />
 *
 * Pass `embedded` to hide the module's own sidebar when it is rendered
 * inside a shared application layout.
 */
export default function SuperuserDashboard({ embedded = false }) {
  return <SuperuserApp embedded={embedded} />;
}

