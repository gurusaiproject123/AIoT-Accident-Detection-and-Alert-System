# Authentication and API integration README

This README maps the frontend modules that must work with authentication in the AIoT Accident Detection and Alert System. It follows **STEPS FOR FRONTENDS.docx**, using **hospital apis.docx** for hospital endpoints and data relationships, and the current frontend code for implementation status.

The documents are planning references. Their branch, installation, commit and submission instructions are documented here as future integration steps; creating this README does not execute them or implement authentication.

## Current status

- `frontend/src/pages/auth/Login.jsx` and `Login.css` provide a demo login form. Sign-in is simulated; the `aiot.preview.signedIn` localStorage flag is not an authenticated session.
- `frontend/src/App.jsx` exposes `/hospital`, `/superuser` and `/vehicle` as unprotected development placeholders.
- The Supabase client, authentication context, route guard and real API integrations remain to be implemented. See [auth.md](auth.md) for the existing login setup notes.

## Authentication flow shared by the modules

1. The user enters email and password in `Login.jsx`. There is no role selector.
2. The Supabase client signs in and obtains a session access token.
3. `AuthContext.jsx` requests `GET /api/auth/me` with `Authorization: Bearer <access_token>`.
4. FastAPI verifies the token and retrieves the trusted application role and hospital assignment from `profiles`.
5. The frontend waits for the verified profile before opening a dashboard:

   | Verified role | Destination |
   | --- | --- |
   | Superuser | `/superuser` |
   | Hospital staff | `/hospital` |
   | No assigned role | Access-not-assigned message; no dashboard access |

6. Protected API requests use the current access token. FastAPI enforces role, hospital and resource permissions on every request.
7. Session restoration, token refresh and sign-out update the shared auth state. Logout clears profile information and protected page data and returns the user to `/login`.

The documents describe role meanings but do not fix their serialized values or the `/api/auth/me` response schema. The existing `auth.md` proposes `superuser`, `hospital_staff` and `null`; confirm these with the backend before implementation.

## Shared authentication modules to connect

Paths below are relative to `frontend/src`. Files marked **planned** are integration targets, not working features.

| Module / file | Connection | Responsibility alongside auth |
| --- | --- | --- |
| `pages/auth/Login.jsx` — existing demo | Supabase email/password sign-in | Validate inputs, show pending/error states, replace simulated sign-in, and wait for the verified profile before navigation. |
| `pages/auth/Login.css` — existing | No API | Style the login, loading and feedback states for phone and laptop screens. |
| `services/supabase.js` — planned | Supabase Auth | Initialize the client using the project URL and public publishable key; support session persistence, refresh and sign-out. Never expose a secret or service-role key. |
| `contexts/AuthContext.jsx` — planned | Supabase session events and `GET /api/auth/me` | Restore sessions and share user, verified role, hospital assignment, loading and error states. Clear stale profile data on account changes or logout. |
| `components/ProtectedRoute.jsx` — planned | Shared auth context | Wait for checks, redirect signed-out users, and allow only the verified dashboard role. Block access when profile verification fails. |
| `App.jsx` — existing, integration required | Auth provider and route guards | Wrap the application in the provider and protect `/hospital` and `/superuser`. Vehicle access requires a separate permission decision. |
| Shared API request helper — recommended addition | FastAPI protected endpoints | Attach the current bearer token, handle failed requests consistently, and prevent responses from a previous session populating the current user's screen. A filename is not specified in the documents. |
| Authenticated layout / logout control — planned | Supabase sign-out and shared context | End the session, clear protected data and report failures accurately. |

## Hospital modules and API connections

Planned entry page: `pages/hospital/HospitalDashboard.jsx` with `HospitalDashboard.css`, displayed at `/hospital`.

Every connection below depends on a verified hospital staff profile. The backend must determine the hospital from trusted assignments and check access to each incident or alert; a hospital ID supplied by the browser is not proof of permission.

| Frontend module / action | Endpoint from hospital API document | How it works with auth |
| --- | --- | --- |
| Overview summary cards | `GET /api/hospital/overview` | Return counts for the signed-in staff member's hospital: new alerts, accepted incidents and closed incidents. Confirm response fields with the backend. |
| Assigned incidents / alerts table | `GET /api/hospital/alerts` | Show only alerts available to the assigned hospital. |
| View incident details | `GET /api/incidents/{id}` | Check the staff member's right to view this incident, including any vehicle/contact information. |
| Acknowledge alert | `POST /api/alerts/{id}/acknowledge` | Record the authenticated staff member who saw the alert. |
| Accept response | `POST /api/alerts/{id}/accept` | Record the responding staff member and hospital; validate the current alert state. |
| Decline response | `POST /api/alerts/{id}/decline` | Ask for a reason and record the authenticated responder. Request field names remain to be agreed. |
| Add incident note | `POST /api/incidents/{id}/notes` | Attribute the note to the authenticated user and enforce incident access. |
| Operations history | `GET /api/hospital/activity` | Scope activity to the assigned hospital. |
| Locations and device health | `GET /api/hospital/device-status` | Return only device/location information the hospital is permitted to see. |
| Reports | `GET /api/hospital/reports` | Restrict report data to the hospital's authorized scope. |

For alert action routes, `{id}` identifies the alert; for incident routes, it identifies the incident. The API must provide the appropriate identifiers. After a successful action, refresh affected cards, alerts and details from backend-confirmed state.

## Superuser modules and API connections

Planned entry page: `pages/superuser/SuperuserDashboard.jsx` with `SuperuserDashboard.css`, displayed at `/superuser`. All sections require verified superuser access in both the frontend and FastAPI.

| Frontend module | API connection specified in frontend steps | How it works with auth |
| --- | --- | --- |
| Overview | `GET /api/admin/overview` | Show total incidents, pending alerts, online devices and active hospitals to superusers. |
| Incidents table and details | Admin incident endpoints — paths not specified | Authorize system-wide access to detection, cancellation, hospital responses and escalation history. |
| Devices | Admin device endpoints — paths not specified | Restrict device monitoring and administrative data to superusers. |
| Hospitals | Admin hospital endpoints — paths/methods not specified | Authorize hospital registration, editing and activation/deactivation; audit changes. |
| Users and assignments | Admin user endpoints — paths/methods not specified | Let authorized administrators manage roles and hospital assignments through the backend. Users cannot grant themselves a role. |
| Activity history | Admin audit endpoints — paths not specified | Restrict access to actor, action and timestamp records. |

Agree on the missing contracts before replacing sample data. Do not assume that a hospital detail endpoint grants system-wide admin access.

## Vehicle and device modules that interact with auth

Planned files: `pages/vehicle/VehicleControl.jsx`, `VehicleControl.css` and `services/vehicleApi.js`, displayed at `/vehicle`.

The frontend steps require an authorized operator for cancellation but do not define a vehicle role, operator assignment model or route access rule. Agree on those permissions before enabling real controls.

| Frontend module | Connection from frontend steps | Authentication dependency |
| --- | --- | --- |
| Device selection | `GET /api/devices` | Backend returns devices the authenticated user may access. |
| Device connection, sensors, GPS and detection status | `GET /api/devices/{id}/status` | Check permission for the selected device. Display FastAPI's detection result. |
| Live telemetry and incident updates | Polling or WebSocket interface — contract not specified | Define authentication, subscription scope and session-expiry behavior. Stop subscriptions when access ends. |
| Movement controls | Direct phone-to-ESP32 communication over shared Wi-Fi for the prototype; interface not specified | Agree on command authentication separately. A Supabase browser session does not automatically authorize ESP32 commands. |
| Cancel false alarm | `POST /api/incidents/{id}/cancel` | Backend verifies the operator's permission, incident state and cancellation deadline; UI displays the confirmed outcome. |

Disable movement controls when disconnected and send stop on release or touch cancellation. The ESP32 must also stop when fresh commands stop arriving. Device credentials used to send telemetry to FastAPI are separate from human dashboard authentication.

## Backend data supporting the authenticated modules

These are data relationships from the hospital API document, not instructions to access tables directly from React.

| Tables | Connection to authenticated features |
| --- | --- |
| `profiles` | Links the Supabase user ID to a protected role and hospital assignment. Supports `/api/auth/me` and authorization. |
| `hospitals` | Provides hospital identity, coordinates, contacts and active status for assignments and administration. |
| `vehicle_owners`, `vehicles`, `incident_contacts` | Supply vehicle and authorized contact information; expose only what the user may view. |
| `devices`, `telemetry_packets` | Support device identity, vehicle links, last-seen time and sensor status. Keep device credential hashes out of frontend responses. |
| `incidents`, `alert_attempts` | Supply incident lifecycle, notification status, cancellation and escalation deadlines. |
| `hospital_responses` | Records acknowledgment, acceptance, decline and the responding authenticated user. |
| `incident_actions`, `audit_logs` | Preserve incident timelines and audited administrative actions with actor and timestamp. |

## Integration order and team handoff

The frontend steps assign **authentication and superuser** to Ryan Tsele and Victor Gomwe, **hospital and vehicle dashboards** to Tanatswa and Peter, and **backend, model and connections** to everyone.

1. Complete the login UI, then create the Supabase client, auth context and `/api/auth/me` integration on `frontend-auth`.
2. Agree on role values, profile response fields, hospital assignments and vehicle operator permissions with the backend team.
3. Add route protection and logout. Dashboard teams consume the shared auth context and API helper rather than maintaining separate login state.
4. Connect hospital overview, assigned alerts and details, followed by response actions, notes, history, health and reports on `frontend-hospital`.
5. Connect the superuser overview first, then incidents, devices, hospitals, users and audit history on `frontend-superuser` after their contracts are available.
6. Connect vehicle status, authenticated command transport and cancellation on `frontend-car-control` after agreeing on operator and device permissions.
7. Replace sample data progressively, retaining loading, empty and error states. Document confirmed contracts in each module's README before merging.

Use `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` and `VITE_API_BASE_URL` as described in [auth.md](auth.md). All `VITE_` values are browser-visible. Send the access token in the authorization header, never in a URL or log.

## Acceptance checklist

- [ ] Correct credentials retrieve a verified profile and open the appropriate dashboard; incorrect credentials show an error.
- [ ] Missing roles, failed profile checks and missing hospital assignments do not grant hospital access.
- [ ] Signed-out users cannot access protected routes; hospital staff cannot access superuser routes or APIs.
- [ ] Hospital staff cannot read or modify another hospital's incidents by changing an identifier.
- [ ] Protected API requests use the current token; expired sessions are handled without repeated failing retries.
- [ ] Refresh restores a valid session; logout/account changes clear protected data and live subscriptions.
- [ ] Hospital actions record the authenticated responder and display backend-confirmed results.
- [ ] Superuser role/assignment changes are authorized and audited by the backend.
- [ ] Vehicle access and cancellation enforce agreed operator permissions; late cancellation is rejected by the backend.
- [ ] Phone/laptop layouts, loading, empty and API failure states are verified.
- [ ] After implementation, run `npm.cmd run lint` and `npm.cmd run build` from `frontend`, then submit changes through the relevant frontend branch.

Endpoint payloads, response schemas, pagination, live-update transport and most admin routes are still to be agreed. This README records supplied paths and explicitly identifies the remaining contracts.
