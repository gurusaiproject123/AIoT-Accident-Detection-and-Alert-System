import { Route, Routes } from "react-router";
import SuperuserProvider from "./SuperuserContext";
import SuperuserLayout from "./SuperuserLayout";
import Overview from "./pages/Overview";
import Incidents from "./pages/Incidents";
import IncidentDetail from "./pages/IncidentDetail";
import Devices from "./pages/Devices";
import Hospitals from "./pages/Hospitals";
import Users from "./pages/Users";
import Activity from "./pages/Activity";
import NotFound from "./pages/NotFound";

/**
 * Nested superuser routes. Mounted by App.jsx at `/superuser/*`.
 * Does not create its own BrowserRouter — the app keeps a single router.
 */
export default function SuperuserApp({ embedded = false }) {
  return (
    <SuperuserProvider>
      <Routes>
        <Route element={<SuperuserLayout embedded={embedded} />}>
          <Route index element={<Overview />} />
          <Route path="incidents" element={<Incidents />} />
          <Route path="incidents/:incidentId" element={<IncidentDetail />} />
          <Route path="devices" element={<Devices />} />
          <Route path="hospitals" element={<Hospitals />} />
          <Route path="users" element={<Users />} />
          <Route path="activity" element={<Activity />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </SuperuserProvider>
  );
}

