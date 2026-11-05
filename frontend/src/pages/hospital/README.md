# Connect the hospital dashboard

Copy the ZIP's `frontend/src/pages/hospital` folder into the matching location in your repo. Do not replace `frontend/src/App.jsx`, your auth folder, or your superuser dashboard.

In `frontend/src/App.jsx`, add this import:

```jsx
import HospitalDashboard from "./pages/hospital/HospitalDashboard";
```

If App uses the role route loop from the auth integration, keep its `RequireRole` wrapper and select the hospital component in the existing expression:

```jsx
{role === "hospital_staff" ? (
  <HospitalDashboard />
) : role === "superuser" ? (
  <SuperuserDashboard />
) : (
  <Workspace title={title} />
)}
```

If App declares each route separately, replace its hospital placeholder with this single route (HospitalDashboard includes a role guard):

```jsx
<Route path="/hospital/*" element={<HospitalDashboard />} />
```

Keep the existing AuthProvider. Set `VITE_API_BASE_URL=http://127.0.0.1:8000` in the frontend environment file and restart Vite after edits to that file. Keep the Supabase URL and publishable key already used by the working sign-in. Start FastAPI from `backend` with `./.venv/Scripts/python.exe -m uvicorn app.main:app --reload` in PowerShell. Check `http://127.0.0.1:8000/docs` for the hospital alerts and incidents routers. From `frontend`, run `npm run dev`.

## Verify with a test incident

1. Sign in as active hospital staff assigned to a test hospital and open `http://localhost:5173/hospital`. Check that the Network tab shows a 200 for `GET /api/hospital/alerts`. An empty list means no alerts are assigned to this hospital.
2. Route a test incident to this hospital through the existing backend workflow. A new alert should appear on the next refresh (about 10 seconds), with its server deadline. Click once in the page to allow browser alarm audio.
3. Open the alert and acknowledge it. Accept it, or use a separate acknowledged alert to test declining. Check that the action is recorded after reloading. Verify that another hospital's staff cannot open or act on that alert.
4. Test an incident with GPS and one without GPS. Coordinates and a map link only appear when available.

Alert actions use the notification UUID; incident notes, reports, timelines and closure use the incident UUID. The workspace does not create demo alerts. Incident routing and escalation still run in the backend.
