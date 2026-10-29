# Hospital Dashboard Frontend

Part of the **AIoT Accident Detection and Alert System**, built by AI GURUS.

This React module helps staff review suspected accidents assigned to **one hospital**, inspect incident and vehicle information, acknowledge an alert, and record the hospital’s response.

**Current status: working frontend demonstration.** It uses fictional records stored in the browser. It is not connected to FastAPI, Supabase Auth, ESP32 telemetry or live hospitals. Adding a demo alert does not detect a real crash or notify another hospital.

## 1 Start here

From the repository root, open a terminal and run:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open the address printed by Vite, then visit `/hospital`.

Use `npm.cmd` in Windows PowerShell if `npm` is blocked by the script execution policy. This runs the same npm commands without changing that policy.

## 2 Pages and their purpose

| Page | Route | What it does |
|---|---|---|
| Overview | `/hospital` | Shows incident counts, recent alerts and response activity. |
| Assigned incidents | `/hospital/incidents` | Searches by incident ID, device or location and filters by status. |
| Incident details | `/hospital/incidents/:incidentId` | Shows one incident and its response controls. Example: `/hospital/incidents/INC-1048`. |
| Operations | `/hospital/operations` | Shows hospital action history and workspace preferences. |
| Locations and health | `/hospital/health` | Shows sample locations and associated device IDs; live connection status is not measured. |
| Reports | `/hospital/reports` | Shows status totals and exports incident records to CSV. |

Old `/hospital/alerts`, `/hospital/map`, `/hospital/history` and `/hospital/settings` links redirect to the corresponding current pages.

## 3 How an incident moves through the demo

### New alert

Click **Add demo alert** on Assigned incidents. The new record appears with a three-minute acknowledgment countdown. Once browser audio is activated, the alarm repeats and the animated ring shakes while New alerts remain.

### Acknowledge receipt

Open **View details**, click **Acknowledge**, select a demo staff member and confirm the action using the demo password described below.

Successful acknowledgment records who received the alert and when, stops that incident’s countdown, and removes it from the New alert count. The alarm stops only when there are no other New alerts.

**Acknowledgment means the hospital has received the alert. It does not mean the hospital has accepted a response.** Opening the confirmation form alone does not acknowledge anything; the deadline continues until confirmation succeeds.

### Accept or decline

After acknowledgment, staff can:

- **Accept response:** record the hospital’s agreement to respond. This does not dispatch an ambulance or prove one has been dispatched.
- **Decline:** enter a mandatory reason and confirm. The demo records an immediate simulated escalation to an eligible alternative hospital.

An accepted incident can later be closed. Notes and possible-false-alarm reports also require staff confirmation. A false-alarm report requests review; it does not globally cancel an incident.

### No acknowledgment within three minutes

A New alert that reaches its deadline enters simulated escalation. Acknowledged alerts no longer time out. An acknowledgment attempted at or after expiry cannot override the expired deadline.

The demo ranks active, untried hospitals using straight-line distance. Missing GPS or no eligible alternative produces **Escalation pending** for manual review. No real notification is delivered. Production timers and routing must run durably in FastAPI/backend services, including when this browser is closed.

## 4 Staff confirmation during testing

For response actions, choose an active name from the staff dropdown and use this **public demo password**:

```text
DemoConfirm!2026
```

An incorrect password or Cancel leaves the incident unchanged. The selected name and action time appear in the response history.

This shared fixture password is not real authentication. Do not enter personal passwords. Production must verify the signed-in staff member through Supabase/FastAPI and derive their identity and hospital from the verified session, rather than trusting a dropdown selection.

## 5 Information shown in incident details

- Incident, reported and assigned times, with available timestamp provenance.
- GPS coordinates, availability and location age; missing accuracy is not invented.
- Device ID, Random Forest model score and peak acceleration.
- Vehicle registration, make, model and colour.
- Registered owner’s name, relationship, phone and email.
- Acknowledgment deadline, response information, escalation details, notes and action history.

The registered owner is not assumed to be the driver or an occupant. Contact details are fictional placeholders. A model score is not a calibrated crash probability, injury-severity rating or clinical priority.

The location preview is a **schematic**, not a geographically accurate map. Coordinate links can open a separate map service. Where an older record lacks an incident timestamp, any use of reported time is labelled as an estimate.

## 6 Alarm behaviour

The alarm stays armed; there is no Mute/off toggle. The first pointer or keyboard interaction activates browser audio automatically. Clicking **Add demo alert** counts as that interaction.

- New incident: repeating sound and stronger ring animation.
- All New incidents acknowledged: sound stops; the alarm remains ready.
- Another New incident: sound starts again without a separate Enable step.
- **Test alarm:** checks audio; it does not disable the alarm.

A fresh page cannot guarantee sound before the browser receives a user interaction. Background tabs, blocked site audio or a sleeping device can interrupt playback. Reduced-motion and animation preferences affect visual movement, not the incident state.

## 7 Files and where to make changes

All hospital code stays together in `frontend/src/pages/hospital/`.

| File or folder | Responsibility |
|---|---|
| `HospitalDashboard.jsx` | Small compatibility entry point used by the main app. |
| `HospitalApp.jsx` | Hospital routes and shared provider. |
| `HospitalLayout.jsx` | Sidebar, header, page headings, alarm banner and confirmation interface. |
| `HospitalContext.jsx` | Shared incidents, response actions, alarm, countdown, escalation and export behaviour. |
| `data.js` | Demo hospital/staff/vehicle records and data, validation, routing and export helpers. |
| `HospitalDashboard.css` | Hospital styling, responsive layouts and animations. |
| `components/Background.jsx` | Ambient visual background. |
| `components/ui.jsx` | Reusable icons, badges, ring, table and other shared UI. |
| `pages/` | Overview, Incidents, IncidentDetail, Operations, Health and Reports screens. |
| `assets/` | Bundled medical background image. Copy this folder too. |

Edit the relevant page for a screen change, shared UI for reused visuals, and Context/data helpers for workflow behaviour. Do not put the entire module back into HospitalDashboard.jsx.

## 8 Connect the module to the main application

Keep the existing `main.jsx`. In `App.jsx`, use your existing BrowserRouter and add:

```jsx
import HospitalDashboard from "./pages/hospital/HospitalDashboard";

// Inside your existing <Routes>:
<Route path="/hospital/*" element={<HospitalDashboard />} />
```

The `/*` allows hospital subpages to work. Remove duplicate hospital placeholder routes. The hospital provides its own sidebar/header, so render it outside the old shared sidebar layout. Do not add another BrowserRouter or copy the standalone package’s main.jsx/reset.css over your existing files.

## 9 Storage and CSV reports

Demo incidents persist in this browser’s localStorage under `aiot-hospital-demo-v1`. Different browsers and computers do not share these records. Operations includes **Reset demo**, which restores fictional records and removes local demo response history.

CSV exports hospital incident records, including available times, location, model values, vehicle/owner details, response actors, escalation and audit history. Nested records are represented inside CSV cells. Passwords are not part of the export. These browser records are not a production database or a tamper-proof audit trail.

## 10 Backend work still required

Agree on the final API contract with the backend team. The following endpoints describe the planned integration; they are not currently called by this demo.

| Planned endpoint | Purpose |
|---|---|
| `GET /api/auth/me` | Verified user role and hospital assignment. |
| `GET /api/hospital/alerts` | Alerts assigned to that hospital. |
| `GET /api/alerts/{id}` | Authorised alert details. |
| `POST /api/alerts/{id}/acknowledge` | Confirm receipt. |
| `POST /api/alerts/{id}/accept` | Accept the response. |
| `POST /api/alerts/{id}/decline` | Decline with a reason. |

The demo uses incident IDs; the backend may provide separate alert IDs. Store both and send the appropriate ID for each endpoint.

Replace local actions with API requests, add pending/error/reconnect states, and update the screen only after server confirmation. Use WebSocket updates or agreed polling for incoming alerts. FastAPI must enforce hospital isolation, roles, valid transitions, staff identity and atomic deadline/response handling. Keep private Supabase keys out of React.

Hospital registration, cross-hospital user administration and global routing rules belong to the superuser module.

## 11 Features not implemented in this frontend

Do not describe these as working features until they are built and tested:

- Live sensor ingestion, model inference or emergency-service delivery.
- Priority filtering, automatic urgency sorting or clinical triage.
- An Under review status or an acceleration time-series chart.
- Real ambulance dispatch, global false-alarm cancellation or secure staff login.
- A geographic live map or genuine device/network health monitoring.

## 12 Test before opening a pull request

1. Run the app and open every hospital page, including a direct incident URL.
2. Add a demo alert and check the countdown, alarm and ring animation.
3. Try a wrong confirmation password, then correctly acknowledge the alert. Check that the timer clears and the recorded name/time appears.
4. Verify acceptance is separate from acknowledgment. Test a reasoned decline on another acknowledged record.
5. Leave a separate New alert unanswered for three minutes and inspect simulated escalation. No live hospital should be contacted.
6. Check search, status filters, vehicle/owner details, CSV export and phone layout.
7. Run the project’s checks from `frontend`:

```powershell
npm.cmd run lint
npm.cmd run build
```

Review your changes, commit them to `frontend-hospital`, push and open a pull request into `main`. Include completed features, test steps, check results and pending integrations. Do not commit node_modules, dist, real contact data or private environment files.
