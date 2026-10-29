# Superuser frontend — staff and car-owner account management

This module belongs in frontend/src/pages/superuser/. Its glass background, fonts, colours and animations are unchanged. It remains a browser-local DEMO. FastAPI, Supabase email/password account creation and the separate car-owner vehicle interface are not connected/generated here.

## Confirmed roles

| Role | Hospital assignment | Owner/vehicle relationship | Interface |
|---|---|---|---|
| hospital_staff | Exactly one hospital; several staff can share it | Assigned emergency information only | Hospital dashboard |
| superuser | None | System monitoring; no driving controls | Superuser dashboard |
| car_owner | None | One registered owner identity with one or more cars | Separate vehicle interface |

The superuser creates hospital staff AND car-owner login accounts. No public owner self-registration, extra job-based roles or owner-to-hospital relationship is assumed. An owner contact record can exist before a login; creating an owner login requires selecting that registered owner with at least one car. Multiple cars reuse the same registered owner identity, not separate logins.

## Install

1. Back up/commit the current module, then replace the complete frontend/src/pages/superuser/ folder with superuser/ from this ZIP.
2. Keep main.jsx, index.css, shared Auth and the existing BrowserRouter.
3. Mount /superuser/* to SuperuserDashboard in App.jsx as before. Do not add another router inside this module.
4. Delete obsolete pages/VehicleControl.jsx if left over from the earlier copy. There is no superuser driving route/nav entry.
5. Run npm.cmd run dev from frontend.

No new dependency is required beyond your existing React/React DOM/react-router app. No database is modified by this ZIP. Use the corrected supabase.zip migrations separately.

## Demo account form

Users and roles offers Hospital staff, Superuser and Car owner. Staff require a known hospital. Administrators and owners have the hospital selector cleared/disabled. Car owners require a registered-owner selection; the selector shows owner name and associated car registrations. A second login for the same owner record is rejected. The user list includes a Car owners tab and Owner/cars column. Owner selection is not a field stored in the real profiles table: the real relationship is vehicle_owners.user_id; the demo flattens it to ownerId.

The supplied owner options are FICTIONAL fixtures based on the existing sample vehicles. In the real app, load registered owners and their cars from protected FastAPI endpoints. Real owner/car registration (name, phone, contact email, registration, make/model/colour, device) must create the existing vehicle_owners/vehicles/devices records first; this ZIP does not add those registration screens or assign a real vehicle to an arbitrary email.

The form saves LOCAL DEMO PROFILES ONLY. It does not create a Supabase login, set a password or send an invitation. Safe-field persistence excludes passwords/tokens. Do not add credentials to data.js or localStorage. Existing demo records are retained and invalid assignments are flagged rather than guessed. Three staff at one hospital is supported, not required as a minimum/maximum.

Hospital cards keep active staff counts and View staff links. Those counts include hospital_staff only, not car owners or administrators. Staff/admin account rules from the previous version are preserved.

## Real email/password integration

The shared Auth module uses Supabase signInWithPassword({email,password}). FastAPI verifies the JWT and loads the protected profile plus hospital/owner relationships. Route hospital_staff to /hospital, superuser to /superuser, car_owner to the separate /vehicle module. Creating owner accounts does not mean driving controls belong in the superuser dashboard.

api.js includes a planned createUser(token,{name,email,role,hospitalId,ownerId,password}) helper for POST /api/admin/users. It is NOT called by the demo form. FastAPI must verify active superuser access, validate the owner/hospital relationship, follow the database account-provisioning workflow, create the Supabase Auth account, link the owner atomically and audit the action. Only collect/transmit an initial password in the real protected HTTPS flow; clear it afterward and never pass it to demo persistence. Service keys stay on the backend.

GET /api/admin/users should return a joined/flattened ownerId and permitted car list for display. Map real UUIDs and snake_case fields to this demo's camelCase shape. Demo IDs like OWN-001 and HSP-001 are NOT database UUIDs. Role/owner-link changes must update profiles and vehicle_owners consistently in a backend transaction; the old generic updateUser helper does not implement that transaction or field mapping.

To use the optional route guard, supply a backend-verified profile:

```jsx
<SuperuserDashboard
  demoMode={false}
  authLoading={authLoading}
  currentUser={verifiedProfile ? {
    role: verifiedProfile.role,
    status: verifiedProfile.status,
    hospitalId: verifiedProfile.hospital_id,
  } : null}
/>
```

Default demoMode=true preserves the standalone preview; it is NOT a protected deployment. The guard denies staff, owners and suspended/invalid admins, but only gates this demo UI. FastAPI must enforce authorization independently. The sidebar Open login (demo) link does not sign out a real session: wire the shared supabase.auth.signOut handler during integration.

## Monitoring and routes

/superuser: overview; /incidents and /incidents/:incidentId: flow/details; /devices: status; /hospitals: registry; /users: account assignments; /activity: audit/preferences. These paths are relative to /superuser. /superuser/users?hospital=HSP-001 filters staff by hospital. There is no /superuser/vehicle page.

Simulate detection creates a 30-second false-alarm cancellation window with no hospital notification yet. The superuser sees the banner/countdown and incident details. If uncancelled it proceeds to simulated hospital routing. Owner/device cancellation belongs to the separate vehicle workflow. The hospital's three-minute acknowledgment deadline is different from the 30-second false-alarm window.

This local demonstration does not synchronize the hospital dashboard or another browser. Durable countdowns, cancellation authorization, scheduling and real notification fan-out belong to FastAPI. No physical driving or owner login page is provided by this module.

## Tests and verification

From frontend:

```powershell
node --test src/pages/superuser/tests/userRules.test.mjs
npm.cmd run build
```

Ten targeted tests passed, including owner identity/car requirements, hospital exclusion and owner rejection by the admin guard. The standalone Vite build passed. Browser checks verified selecting Car owner disables hospital assignment, missing owner linkage blocks saving, and a linked demo owner appears under Car owners with its registration. CSS/background assets were compared byte-for-byte with the previous version and remain unchanged.

Not executed: live Supabase authentication/account creation, database RLS tests, FastAPI integration or the separate owner driving interface. The corresponding SQL package supplies development owner-isolation tests to run after migrations 07 and 08.
