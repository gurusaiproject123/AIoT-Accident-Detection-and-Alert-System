import RequireRole from "../auth/RequireRole";
import SuperuserApp from "./SuperuserApp";
import "./SuperuserDashboard.css";

export default function SuperuserDashboard({ embedded = false }) {
  return <RequireRole roles={["superuser"]}><SuperuserApp embedded={embedded} /></RequireRole>;
}
