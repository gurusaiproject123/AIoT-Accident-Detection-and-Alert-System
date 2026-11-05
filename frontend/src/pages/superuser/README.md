# Connect the Superuser dashboard

1. Start from a branch based on the working main, e.g. frontend-superuser-integration.
2. Merge the contents of this archive's frontend/src/pages/superuser folder
   into the same folder in your project.
3. Keep your working frontend/src/main.jsx and frontend/src/pages/auth/.
   This dashboard uses the existing AuthProvider and Supabase session.
4. In your working frontend/src/App.jsx, add:
   
   ```jsx
   import SuperuserDashboard from "./pages/superuser/SuperuserDashboard";
   ```

   Replace the existing /superuser/* placeholder with:
   
   ```jsx
   <Route path="/superuser/*" element={<SuperuserDashboard />} />
   ```
   
   If the routes are generated from a pages array, remove the superuser entry
   from that mapping after adding the explicit route. Keep login and the
   other dashboard routes. The SuperuserDashboard already applies RequireRole.
5. Run FastAPI on port 8000, keep your working frontend/.env.local, and run
   npm.cmd run dev from frontend. Sign in as a superuser. Check browser Network
   for GET /api/admin/overview and GET /api/admin/incidents, then open one
   incident and confirm its details and timeline load.

Connected: overview, incident lists/details/timeline, incident notes/routing/
closure, devices, hospital registration/status and updates, account creation
and status, staff hospital reassignment, and audit history. Manual refresh
fetches current records. The countdown displays the server's deadline; the
backend owns expiry and notifications.

The current hospital list API returns summary fields only. Missing contact,
coordinate, and registration-date values are not inferred. Enter both
coordinates to update them, or leave both blank when editing to preserve them.
Staff and owner login creation are supported; creating another superuser or
editing an existing account's role/name/email is outside the available API.
The dashboard does not include demo records or simulated incident creation.

Checks: Vite build and 18 auth/dashboard rule tests passed in the local
integration harness. No live Supabase records were created or modified.
Verify read endpoints first, then exercise write actions using test records
in your development backend.
