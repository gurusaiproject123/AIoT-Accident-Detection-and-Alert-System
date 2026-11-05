import RequireRole from "../auth/RequireRole";
import HospitalApp from "./HospitalApp";

export default function HospitalDashboard(props) {
  return <RequireRole roles={["hospital_staff"]}><HospitalApp {...props} /></RequireRole>;
}
