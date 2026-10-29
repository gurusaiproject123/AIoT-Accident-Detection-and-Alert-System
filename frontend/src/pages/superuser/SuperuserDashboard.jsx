import { Navigate } from "react-router";
import SuperuserApp from "./SuperuserApp";
import { canOpenSuperuser } from "./userRules";
import "./SuperuserDashboard.css";

/** Existing preview defaults to demoMode. For Auth integration pass demoMode={false},
 * authLoading and a backend-verified currentUser {role,status,hospitalId}.
 * This gates only the demo UI; FastAPI must enforce real permissions. */
export default function SuperuserDashboard({ embedded = false, demoMode = true, currentUser = null, authLoading = false }) {
  if (authLoading) return <p role="status">Checking administrator access…</p>;
  if (!demoMode && !currentUser) return <Navigate to="/login" replace />;
  if (currentUser && !canOpenSuperuser(currentUser)) return <section role="alert"><h1>Administrator access required</h1><p>This monitoring workspace requires an active superuser with no hospital assignment.</p></section>;
  return <SuperuserApp embedded={embedded} />;
}
