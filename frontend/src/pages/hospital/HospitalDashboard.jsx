// Compatibility entry point: existing App.jsx imports can stay unchanged.
import HospitalApp from "./HospitalApp";
export default function HospitalDashboard(props) {
  return <HospitalApp {...props} />;
}
