# Authentication UI and remaining setup

## Current implementation

This change is strictly frontend UI. `/login` provides a responsive email/password form, browser validation, password visibility control, and an accessible feedback area. `/` opens the login screen.

The form now simulates sign-in with an 800ms loading state and disabled submission/fields. Use `demo@example.org` and `DemoPreview123!` for success; other credentials show an error. These are public demo values, not real account credentials. No network request is made. Only the string `true` is saved under `aiot.preview.signedIn` in localStorage; passwords, email addresses, tokens, and roles are never saved. Refresh restores the demo success message. The Clear demo session button removes the flag, and storage failures display an error. This flag grants no dashboard permissions and must not be used as proof of authentication. Replace this simulation with the real integration described below.

Existing `/hospital`, `/superuser`, and `/vehicle` pages remain development previews and are not protected. There is no role selector. No Supabase library, client, auth context, route guard, or backend code has been added. Those files should be created when real authentication is connected, so empty utilities cannot be mistaken for working security.

## Steps requiring your attention

1. Create or select a Supabase project and enable email/password authentication. Provision test accounts for a superuser, hospital staff member, and user with no assigned role. Assign roles through trusted administration, never through the login form.
2. Inside `frontend`, run `npm.cmd install @supabase/supabase-js` when ready to integrate authentication.
3. Create a local `frontend/.env.local` file using the dummy configuration below. Replace all placeholders. Never use a secret or service-role key in frontend code. All `VITE_` values are public in the browser.

   ```dotenv
   VITE_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
   VITE_SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLIC_PUBLISHABLE_KEY
   VITE_API_BASE_URL=http://localhost:8000
   ```

4. Create `frontend/src/services/supabase.js`. Initialize the Supabase client from those environment variables, handle missing configuration clearly, and enable session persistence and token refresh. Restart Vite after changing environment values.
5. Arrange the backend integration separately. This repository currently has no backend. Agree on `GET /api/auth/me`, accepting `Authorization: Bearer <access_token>`. A proposed response contract is below; confirm the exact field names and role values before connecting the frontend.

   ```json
   {
     "user": { "id": "EXAMPLE_USER_ID", "email": "staff@example.org" },
     "role": "hospital_staff",
     "hospital_id": "EXAMPLE_HOSPITAL_ID"
   }
   ```

   Proposed role values: `superuser`, `hospital_staff`, or `null`. The backend must verify token validity, read trusted application role/hospital assignments, return appropriate unauthorized/forbidden errors, and enforce permissions on every protected endpoint. Browser role checks alone do not secure data. Configure allowed frontend origins for CORS; use HTTPS in production.
6. Create `frontend/src/contexts/AuthContext.jsx`. Restore the existing session on startup, subscribe to auth changes, fetch the verified profile with the access token, and share user, role, hospital assignment, loading, and error states. Clear profile information immediately when the session ends or changes. Unsubscribe on unmount and prevent outdated profile requests from restoring stale permissions.
7. Replace the placeholder submit handler in `Login.jsx` with `signInWithPassword`. Keep required-field validation, disable submission while pending, display `Signing in…`, and show useful errors without logging credentials or tokens. Wait for the backend profile before navigation. Redirect superusers to `/superuser` and hospital staff to `/hospital`. Show an access-not-assigned message for users without an assigned role; never invent a fallback role.
8. Create `frontend/src/components/ProtectedRoute.jsx` and wrap dashboard routes in `App.jsx`. Wait for authentication/profile checks; redirect signed-out users to `/login`; restrict each dashboard to its verified role. Block access on profile lookup failures. Decide vehicle access separately with the project owner.
9. Add logout to the authenticated layout. Sign out through Supabase, clear the profile, and return to `/login`. Display failures rather than claiming logout succeeded. Remove the development preview wording only when the integration actually works.

## Verification

For the current UI, check `/login` at laptop and phone widths, keyboard focus order, show/hide password, required fields, and invalid email. Submit the public demo credentials to check loading, disabled controls, success, refresh persistence, and clearing the saved flag. Submit different credentials to check failure. Block browser storage to check storage errors. Navigate away during loading to check timer cleanup. No real credentials are needed.

After integration, test correct/incorrect credentials, both role destinations, users without roles, expired sessions, unavailable profile service, direct protected URLs while signed out, hospital staff accessing `/superuser`, session restoration on refresh, and logout. Verify backend authorization independently.

Run from `frontend`:

```powershell
npm.cmd run dev
npm.cmd run lint
npm.cmd run build
```

Review and commit the frontend files and this document on `frontend-auth`, push that branch, and open a pull request into `main`. Exclude local environment files and credentials.
