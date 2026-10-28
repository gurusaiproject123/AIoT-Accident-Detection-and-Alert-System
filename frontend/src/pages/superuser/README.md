# AIoT Accident Detection and Alert System
## Superuser Dashboard Frontend

The superuser (admin) dashboard gives system administrators a complete view of the platform: every suspected accident from detection to hospital response, ESP32 device health, the hospital notification network, user roles and an activity history.

This module is a **React demonstration using fictional incidents, devices, hospitals and contacts**. FastAPI, Supabase authentication, the ESP32 and live notifications are not connected yet. Sample hospital names do not imply any actual partnership.

Owner: Victor Gomwe (Superuser and Auth team) · Branch: `frontend-superuser`

## Current features

- **Overview** — Total incidents, Pending alerts, Online devices and Active hospitals cards; recent incidents; incident-flow breakdown; "needs attention" list; device, hospital and activity summaries.
- **Incidents** — Incident ID | Device | Time | Location | Status | Action table with search, status groups and hospital filter.
- **Incident details** (direct URL) — detection information and location, cancellation status with live countdown, hospitals notified with acknowledgment/acceptance times, full escalation history, manual routing to another hospital, notes and closure.
- **Devices** — connection status, last-seen time, GPS status, last location and firmware.
- **Hospitals** — list, register, edit and activate/deactivate (with validation and confirmation).
- **Users and roles** — authorised role and hospital assignment, add/edit, suspend/reactivate. At least one active superuser must always remain.
- **Activity history** — who performed each action and when, category filter, search and CSV export. Includes workspace preferences and Reset demo.
- **Simulate detection** — creates a demo incident with a 30-second cancellation window; when it expires the nearest active hospital is notified automatically.
- Pending-alert bell, cancellation-window banner, toasts, responsive sidebar, floating background, reduced-motion support and localStorage persistence.

## Folder structure

```text
frontend/src/pages/superuser/
├── README.md
├── SuperuserDashboard.jsx    Entry point used by App.jsx
├── SuperuserDashboard.css    All module styles (scoped under .su-root)
├── SuperuserApp.jsx          Nested routes + provider
├── SuperuserLayout.jsx       Sidebar, top bar, bell, banner, toasts
├── SuperuserContext.jsx      SuperuserProvider: state, actions, persistence
├── useSuperuser.js           Context object + useSuperuser() hook
├── data.js                   Fictional records, vocabularies, helpers
├── api.js                    FastAPI endpoint placeholders (not used yet)
├── components/
│   ├── Icon.jsx              Inline SVG icon set
│   ├── ui.jsx                Badges, panels, stat cards, modal, table, ring…
│   ├── Background.jsx        Floating background effects
│   ├── HospitalForm.jsx      Register / edit hospital dialog
│   └── UserForm.jsx          Add user / edit role dialog
└── pages/
    ├── Overview.jsx
    ├── Incidents.jsx
    ├── IncidentDetail.jsx
    ├── Devices.jsx
    ├── Hospitals.jsx
    ├── Users.jsx
    ├── Activity.jsx
    └── NotFound.jsx
```

The hook lives in `useSuperuser.js` (separate from the provider) so React Fast Refresh and the `react-refresh/only-export-components` lint rule stay happy.

## Page routes

| URL | Page |
| --- | --- |
| `/superuser` | Overview |
| `/superuser/incidents` | Incidents |
| `/superuser/incidents/INC-1050` | Example incident details |
| `/superuser/devices` | Devices |
| `/superuser/hospitals` | Hospitals |
| `/superuser/users` | Users and roles |
| `/superuser/activity` | Activity history |

## Connection to App.jsx

```jsx
import SuperuserDashboard from "./pages/superuser/SuperuserDashboard";

<Route path="/superuser/*" element={<SuperuserDashboard />} />
```

`/*` lets the nested pages resolve. The route sits **outside** the shared placeholder layout because the module has its own sidebar. If the team later wants the shared sidebar instead, use `<SuperuserDashboard embedded />`. Keep a single `BrowserRouter` in the app.

## Run

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open `http://localhost:5173/superuser`.

## Demo storage and reset

Storage key: `aiot-superuser-demo-v1`. Data are local to this browser only. Use **Activity history → Reset demo** to restore the initial records.

## Theme

Matches the hospital workspace: deep teal sidebar (`#0d2627`), mint accent (`#6fd6bd`), primary teal (`#14605a`), off-white canvas (`#f4f7f7`) and pastel status tones (red, amber, green, blue, purple, grey). Variables are declared at the top of `SuperuserDashboard.css`.

## Backend integration remaining

1. Protect `/superuser/*` with the auth team's `ProtectedRoute` (role = superuser).
2. Replace fixtures with `api.js` calls, starting with `GET /api/admin/overview`, then incidents, devices, hospitals, users and audit.
3. Add loading, empty, error and retry states; only show completed actions after server confirmation.
4. FastAPI must verify superuser access and own routing, escalation, cancellation deadlines and the audit trail. Hiding controls in React is not access control.
5. Never put Supabase secret/service-role keys in React.
6. Replace device placeholders with real heartbeat and GPS data.

## Validation

```powershell
npm.cmd run lint
npm.cmd run build
```

### Manual checklist

- [ ] Overview counts match the records.
- [ ] Incident search and filters work; direct incident URLs survive refresh.
- [ ] Simulate detection → countdown banner → nearest hospital notified at 0s.
- [ ] Manual routing adds a notification and escalation entry.
- [ ] Close incident and notes appear in history and Activity.
- [ ] Hospital register/edit validation; deactivation removes it from routing.
- [ ] Hospital staff require a hospital; last superuser cannot be demoted or suspended.
- [ ] CSV export downloads.
- [ ] Mobile menu works without horizontal page scrolling.

## Git handover

```powershell
git add frontend/src/pages/superuser/ frontend/src/App.jsx
git commit -m "Add superuser dashboard module"
git pull --no-rebase origin frontend-superuser
git push origin frontend-superuser
```

Open a pull request from `frontend-superuser` into `main` and ask a teammate to review.

