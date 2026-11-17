# Local MySQL on WAMP

The local provider replaces Supabase database access and password login. FastAPI
and Vite still run separately from WAMP. Only WAMP's MySQL service is needed;
Apache and MariaDB are not required. The ESP32 continues to call FastAPI, using
the same device UUID and credential. Do not expose MySQL directly to the car.

## Starting the application after cutover

Start WAMP's `wampmysqld64` service. From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-mysql.txt
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm.cmd run dev -- --host 0.0.0.0
```

The frontend uses FastAPI for authentication and all dashboard data. Set
`VITE_API_BASE_URL=` (empty) in `frontend/.env.local`, then restart Vite.
Vite development and preview servers forward `/api` to `127.0.0.1:8000`, so
changing the laptop's Wi-Fi address does not break browser requests. When hosting
the built files with Apache, configure the same `/api` reverse proxy to FastAPI.
FastAPI connects to WAMP MySQL;
the browser does not connect directly to MySQL. The frontend has no Supabase
SDK or cloud login fallback. Sessions are stored only in page memory;
refreshing requires login again. Logout revokes the server session. Unload-time
revocation is best effort; unused server sessions expire after eight hours.

## Existing accounts

Profile IDs, email addresses, roles, hospital assignments, vehicle ownership and
device credential hashes are imported unchanged. Supabase login password hashes
cannot be exported using the API key, so local accounts receive unique temporary
passwords in `migration-private/temporary-logins.json`. This private file must not
be committed or shared as a whole. Give each account holder only their own entry.
The first login requires replacing the temporary password (12–128 characters).
Passwords are stored as salted scrypt hashes. Only hashes of session tokens are
stored. Failed logins are rate-limited by account identifier.

For local password recovery, run from `backend`:

```powershell
..\.venv\Scripts\python.exe scripts/set_local_password.py
```

This interactive maintenance command prompts for an existing email and a new
password, and revokes that user's sessions. Do not use the old Supabase-specific
`create_admin.py` helper for local accounts. Imported administrators can create
hospital and owner accounts through the admin dashboard.

## Migration and verification

`migration-private` is excluded from Git. It contains the API export, checksums,
private local settings, temporary passwords and verification reports. A service
role API export cannot retrieve PostgreSQL function bodies, RLS policies, or Auth
password hashes. Application rules have therefore been rebuilt in `app/localdb`;
this is not a byte-for-byte port of inaccessible PostgreSQL functions.

The source backend and ESP32 must remain stopped through final verification and
configuration switching. The export is not a transactionally consistent snapshot
across tables. Mutable tables are rechecked against the stopped source; sensor
history is append-only in this application and is checked by count/high-water ID.
Every exported field is separately compared with its imported MySQL value.

The migration preserves all 17 public application tables, including telemetry
and audit history. Foreign keys, uniqueness rules, allowed status values and
application transactions protect local writes. Hospital inboxes poll saved
records; local response updates do not rely on cloud realtime delivery.

Scripts, run from `backend`:

1. `scripts/export_supabase_records.py`: resumable, read-only API baseline export.
2. `scripts/prepare_mysql.py`: prepare the empty target and dedicated app account.
3. `scripts/import_mysql_records.py`: checksummed, resumable import into empty tables.
4. `scripts/check_source_unchanged.py`: check the stopped source against the export.
5. `scripts/verify_mysql_records.py`: compare every imported row and field.
6. `scripts/mysql_constraints.py`: install local indexes and constraints.
7. `scripts/initialize_local_passwords.py`: initialize local credentials once.

`DATABASE_BACKEND=mysql` selects local storage. `mysql.env` contains the generated
settings for this installation. Keep the application account limited to data
operations; schema migration scripts use the local administrator separately.

## Tests

```powershell
$env:MYSQL_TESTS='1'
..\.venv\Scripts\python.exe -m pytest tests/test_mysql_local.py -q
```

These tests create and remove only randomly named `aiot_test_*` schemas. They do
not alter imported application data or Supabase. They cover packet retries,
cancellation, deadline routing, hospital isolation/responses, local authentication,
and HTTP admin/hospital flows. The default test administrator is local root with
no password, matching this WAMP development installation.

## Rollback and backups

Before cutover, `migration-private/backend.env.before-mysql` preserves the previous
backend configuration. Source Supabase records are not deleted. After local use
begins, cloud records become stale: do not switch back without reconciling new
local records. Stop the backend and ESP32 before any rollback.

Back up the MySQL database regularly with WAMP's `mysqldump` tool. Protect private
exports and credentials. If the laptop is off, other devices cannot reach the
local backend. Internet is no longer required for database/login operations;
ESP32 UTC synchronization may still depend on its configured internet NTP servers.
