# AIoT Accident Detection and Alert System
## Hospital Dashboard Frontend

The hospital dashboard helps staff review suspected accident alerts assigned to their hospital, inspect the location and vehicle details, acknowledge receipt, and record a response.

This module is a **React demonstration using fictional incidents and contacts**. FastAPI, Supabase authentication, the ESP32 and live hospital notifications are not connected yet. The sample hospital name does not imply an actual partnership.

## Current features

- Hospital overview with New, Acknowledged, Accepted and Closed incident counts.
- Searchable assigned incidents and status filtering.
- Individual incident pages with direct URLs.
- GPS coordinates, location availability and external Google Maps links.
- Vehicle registration, make, model, colour and linked device ID.
- Registered owner name, phone number and email address.
- Separate acknowledgment and response acceptance.
- Decline with a mandatory reason after acknowledgment.
- Response notes, incident closure and an action timeline.
- Possible false-alarm reporting for review.
- An always-armed repeating alarm and animated warning ring.
- Hospital reports with CSV export.
- Responsive navigation, floating background effects and reduced-motion support.
- Local persistence of demo records and preferences.

## Folder structure

Place this README inside `frontend/src/pages/hospital/`.

```text
frontend/src/pages/hospital/
├── README.md
├── HospitalApp.jsx
├── HospitalLayout.jsx
├── HospitalContext.jsx
├── HospitalDashboard.jsx
├── HospitalDashboard.css
├── data.js
├── components/
│   ├── Background.jsx
│   └── ui.jsx
└── pages/
    ├── Overview.jsx
    ├── Incidents.jsx
    ├── IncidentDetail.jsx
    ├── Operations.jsx
    ├── Health.jsx
    └── Reports.jsx
```

| File | Responsibility |
| --- | --- |
| `HospitalApp.jsx` | Declares hospital routes and mounts the shared provider. |
| `HospitalLayout.jsx` | Sidebar, header, page heading, mobile navigation, alarm banner and notifications. |
| `HospitalContext.jsx` | Shared incident state, response actions, alarm logic, persistence and CSV export. |
| `HospitalDashboard.jsx` | Small compatibility entry point used by the main application. |
| `HospitalDashboard.css` | Hospital layout, page styles, responsive rules and animations. |
| `data.js` | Fictional records, navigation, formatting helpers and migration of older demo records. |
| `components/Background.jsx` | Floating background effects. |
| `components/ui.jsx` | Shared icons, badges, animated ring, incident table and schematic map. |
| `pages/Overview.jsx` | Summary cards and recent incident activity. |
| `pages/Incidents.jsx` | Assigned incident list, search, filters and demo alert creation. |
| `pages/IncidentDetail.jsx` | Vehicle, owner, location and response details for one incident. |
| `pages/Operations.jsx` | Hospital action history and workspace preferences. |
| `pages/Health.jsx` | Incident locations and associated device connection placeholders. |
| `pages/Reports.jsx` | Status breakdown and CSV download. |

## Tools and dependencies

- React and React DOM.
- React Router, imported from `react-router`.
- Vite for development and production builds.
- Plain CSS and inline SVG icons.
- Web Audio API for alarm tones.
- Browser localStorage for demonstration persistence.

The wider project uses FastAPI and Supabase PostgreSQL/Auth. Their integration remains future work in this frontend.

## Run the existing project

Use a VS Code PowerShell terminal. Save or commit unfinished changes before switching branches.

```powershell
cd C:\AIoT-Accident-Detection-and-Alert-System
git switch frontend-hospital
git pull --ff-only origin frontend-hospital
cd frontend
npm.cmd install
npm.cmd run dev
```

Open the local address printed by Vite, followed by `/hospital`. For the usual default port, this is:

```text
http://localhost:5173/hospital
```

Use `npm.cmd` in PowerShell if execution policy blocks `npm.ps1`. If Git reports conflicts or a rejected pull, resolve that issue before continuing.

## Connect this module to App.jsx

Copy the **entire hospital folder**, including its components and pages. Copying only HospitalDashboard.jsx will leave missing imports.

Keep the existing `frontend/src/main.jsx`. Do not replace it with the standalone demonstration entry point.

In `frontend/src/App.jsx`:

```jsx
import HospitalDashboard from './pages/hospital/HospitalDashboard';
```

Inside the existing React Router Routes:

```jsx
<Route path="/hospital/*" element={<HospitalDashboard />} />
```

The `/*` lets hospital subpages resolve correctly. Keep a single BrowserRouter in the application; HospitalApp supplies nested routes and does not create another BrowserRouter.

The hospital module already includes a sidebar and header. Render its route outside the old shared sidebar layout to avoid duplicate navigation. If the team deliberately retains the shared app sidebar, use `<HospitalDashboard embedded />` and add the hospital page links to that shared navigation.

The ZIP's `reset.css` is for its standalone demo. The existing project can keep `index.css`. Remove global Vite starter rules that restrict `#root` width, centre all text or add large outer padding.

## Page routes

| URL | Page |
| --- | --- |
| `/hospital` | Overview |
| `/hospital/incidents` | Assigned incidents |
| `/hospital/incidents/INC-1048` | Example incident details |
| `/hospital/operations` | History and preferences |
| `/hospital/health` | Locations and connection status |
| `/hospital/reports` | Hospital reports |

Older hospital paths redirect for compatibility: `/alerts` to `/incidents`, `/map` to `/health`, and `/history` and `/settings` to `/operations`, all under `/hospital`.

Unknown incident IDs show an unavailable message. Unknown hospital pages show a page-not-found message.

## Incident response workflow

1. Open Assigned incidents and select View details.
2. Inspect the incident location, vehicle and registered contact.
3. Acknowledge the alert to confirm receipt.
4. Accept the response or decline with a reason.
5. Add response notes as needed.
6. Close an accepted incident when the demonstration response is complete.

| Current status | Available status transition |
| --- | --- |
| New | Acknowledged |
| Acknowledged | Accepted or Declined |
| Accepted | Closed |
| Declined or Closed | No further status transition in this prototype |

Acknowledgment confirms receipt; acceptance records willingness to respond. Neither action means an ambulance was dispatched.

Reporting a possible false alarm adds a review entry. It does not globally cancel the incident, silence other New alerts or contact another hospital. Notes and actions are recorded with a demo actor and timestamp.

## Alarm behaviour

The alarm is always logically armed. It has no Mute/off toggle.

1. The first click or key interaction in the dashboard activates browser audio automatically. Clicking Add demo alert also performs this activation.
2. While any assigned incident has status New, a two-pitch alarm pulse repeats approximately every 1.2 seconds.
3. The animated ring shakes, rotates faster and pulses while the audible alarm is active.
4. Acknowledging the final New incident stops the repeating sound and dramatic vibration. The ring returns to gentle ambient movement.
5. The next New incident starts the alarm again without a separate enabling step.

If several incidents are New, acknowledging one does not silence the others. Navigating between hospital pages does not reset the alarm.

Before activation, the interface offers Activate audio. Once ready, it offers Test alarm. When no incident is New, Test alarm plays a short confirmation tone.

**Browser limitation:** a fresh page cannot guarantee audible autoplay before user interaction. Refreshing can require another interaction. Muted tabs, blocked site sound, suspended devices and inactive-tab throttling can affect playback. This browser demo is not a guaranteed unattended emergency alarm service.

The animation preference and operating-system reduced-motion setting disable dramatic movement while preserving static incident information. This is on-screen animation, not physical phone vibration.

### Test the alarm

1. Open Assigned incidents.
2. Click Add demo alert.
3. Confirm the alarm banner appears and the tone repeats.
4. Open Overview to inspect the vibrating ring.
5. Open the New incident and click Acknowledge.
6. If no other New incidents remain, confirm the alarm stops.
7. Add another demo alert and confirm the alarm starts again.

## Vehicle and owner information

Incident details display:

- Registration number.
- Vehicle make, model and colour.
- Linked ESP32/device ID.
- Registered owner name and relationship.
- Phone number and email address.

Current records use fictional `DEMO-...` registrations, placeholder phone numbers and reserved example.com email addresses. They are not actual contacts. The registered owner is not assumed to be the driver or an occupant.

Older cached demo incidents receive their missing sample vehicle/contact fields without deleting response history. Existing populated fields and explicit missing values are preserved. Unknown devices display unavailable information.

During integration, obtain the relevant vehicle and contact information through an authorised backend relation such as device → vehicle → registered owner. Do not commit real contact details into frontend fixtures or store them in this demo's localStorage.

## Map and device information

The built-in map is a labelled schematic. Marker positions are illustrative and are not geographically accurate. Incident details show sample GPS coordinates with an external Google Maps link.

The Health page lists only devices associated with this hospital's demo incidents. It reports live services as not connected; it does not claim to measure actual heartbeats, network health or GPS accuracy.

Replace the schematic and placeholders during integration with a geographic map and validated backend status data. Show missing, outdated and unavailable locations explicitly.

## Demo storage and reset

Demo incidents and animation preferences use this browser storage key:

```text
aiot-hospital-demo-v1
```

Stored data are local to the browser and origin; they are not shared across collaborators, computers or browsers. This storage is not an authoritative database or an access-control mechanism.

To restore the initial incidents, open Operations and choose Reset demo. This clears local demo incident changes and history. Browser audio readiness is session-specific.

## Backend integration remaining

1. Integrate Supabase sign-in and retrieve verified role/hospital assignment through FastAPI.
2. Replace fixture loading with authenticated, hospital-scoped incident/alert queries.
3. Keep incident IDs and alert IDs separate if the API uses different identifiers.
4. Replace local acknowledgment, acceptance and decline actions with server requests. Confirm server success before displaying a completed action.
5. Add loading, request-pending, empty, failure, retry and reconnection states.
6. Connect an authorised live notification channel and deduplicate repeated incident updates.
7. Let the backend own cancellation deadlines, escalation, notification attempts and the audit trail.
8. Fetch vehicle/owner contacts only when authorised for the assigned incident.
9. Enforce hospital isolation and state transitions on the server; hiding controls in React is insufficient.
10. Keep hospital administration, user-role management and global routing in the superuser module.

Supabase secret/service-role keys and private device credentials must not be placed in React. Keep model inference in the agreed backend. A displayed Random Forest score is not a calibrated crash probability or injury-severity estimate.

## Validation

From the existing `frontend` folder:

```powershell
npm.cmd run lint
npm.cmd run build
```

The supplied standalone package passed a production build. Browser checks covered navigation, incident detail URLs, persistence after refresh, response controls, required decline reasons, timeline updates, reports export, responsive layout, automatic audio activation and visual alarm state. Controlled checks covered alarm timer cleanup and migration of older demo records.

Run the team's lint and build checks again after integrating with its shared layout and dependencies. No live FastAPI, Supabase, ESP32 or hospital integration has been validated by these frontend checks.

### Manual checklist

- [ ] Overview counts match the current incidents.
- [ ] Search and status filters return the expected records.
- [ ] Direct incident URLs open and survive refresh.
- [ ] Vehicle registration and owner contacts appear on details.
- [ ] Missing vehicle, contact and GPS data are handled clearly.
- [ ] Acceptance is unavailable before acknowledgment.
- [ ] Decline requires acknowledgment and a reason.
- [ ] Notes and response actions appear in Operations history.
- [ ] New incidents trigger the repeating alarm after browser activation.
- [ ] Acknowledgment of the final New incident stops sound and dramatic vibration.
- [ ] CSV export downloads successfully.
- [ ] Mobile navigation works without page-wide horizontal scrolling.
- [ ] Reduced-motion preferences are respected.

## Git handover

From the repository root:

```powershell
git status
git add frontend/src/pages/hospital/
git diff --cached
git commit -m "Add hospital dashboard pages and incident response workflow"
git pull --no-rebase origin frontend-hospital
git push origin frontend-hospital
```

If App.jsx or index.css was intentionally changed, review and stage those files explicitly before committing. If pulling introduces changes or conflicts, resolve them and rerun the relevant checks before pushing. Never force-push a shared feature branch.

Create a pull request with base main and compare frontend-hospital. Include completed features, browser test steps, validation results and pending integrations. Ask a teammate to review it before merging.

## Troubleshooting

| Problem | Check |
| --- | --- |
| package.json ENOENT | Run npm commands inside `frontend`. |
| npm.ps1 blocked | Use `npm.cmd`. |
| Hospital subpages do not open | Use `/hospital/*` in App.jsx. |
| Missing import/module error | Copy the complete hospital folder. |
| Two sidebars | Render the hospital route outside the old shared layout, or deliberately use embedded mode. |
| Dashboard is squeezed or centred | Check global App.css and index.css rules on `#root` and layout wrappers. |
| No alarm sound | Click in the dashboard, use Activate audio, check volume/tab mute and site sound permissions. |
| Alarm continues after acknowledgment | Other incidents may still have status New. |
| Ring does not vibrate | Check active New alerts, audio readiness, animation preference and reduced-motion settings. |
| Old demo data remain | Refresh after updating files; use Operations → Reset demo only if you want to discard local history. |
| Git says files are untracked | Stage the intended files before committing and pushing. |
