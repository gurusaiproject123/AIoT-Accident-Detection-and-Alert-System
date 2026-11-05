# Backend Module 6: Incidents, Cancellation & History (`backend-incidents`)

This module implements **Section 6 ("Build incidents cancellation and history")** and the shared `incident_service` integration contracts from **Section 9** of the `AIoT_Backend_Branches_and_API_Guide.docx`.

## Implemented API Endpoints

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/incidents` | `superuser`, `hospital_staff`, `car_owner` | List incidents permitted for the caller |
| `GET` | `/api/incidents/{id}` | Permitted caller | Retrieve permitted incident details and honest GPS freshness status |
| `GET` | `/api/incidents/{id}/timeline` | Permitted caller | Retrieve permitted incident event history (`incident_events`) |
| `POST` | `/api/incidents/{id}/cancel` | `car_owner` (owned vehicle only) | Cancel incident during the 30-second local cancellation window |
| `POST` | `/api/devices/{device_id}/incidents/{incident_id}/cancel` | Authenticated ESP32 (`X-Device-Secret`) | Device cancellation for its own incident during the 30-second window |
| `POST` | `/api/incidents/{id}/notes` | Assigned `hospital_staff` or `superuser` | Add an operational note (`incident_notes`) |
| `POST` | `/api/incidents/{id}/false-alarm-reports` | Assigned `hospital_staff` | Submit a false-alarm review report (`false_alarm_reports`, does not cancel incident) |
| `POST` | `/api/incidents/{id}/close` | Assigned responder or `superuser` | Record incident closure (`closed`) |
| `GET` | `/api/admin/incidents` | `superuser` | List all incidents platform-wide |
| `GET` | `/api/admin/incidents/{id}` | `superuser` | Retrieve full incident details, notifications, notes, and false-alarm reports |
| `POST` | `/api/admin/incidents/{id}/close` | `superuser` | Close incident with an explicit outcome and review resolution |

## Shared Python Service Entry Points

- `incident_service.create_from_detection(payload)` — Internal entry point called by `backend-vehicle-ai` when a suspected accident is detected. Deduplicates retried predictions (`prediction_id`, `idempotency_key`, or overlapping active window), stores the absolute 30-second `cancellation_deadline`, labels missing/stale GPS coordinates honestly, and creates no hospital notification before expiry.
- `incident_service.process_due_cancellation_windows()` / `run_cancellation_deadline_tick()` — Durable deadline worker that expires due 30-second windows atomically (racing safely against owner/device cancellation) and initiates hospital routing.
- `incident_service.apply_hospital_response(update)` — Shared service entry called by `alert_service` (`backend-hospital-alerts`) when hospital notifications are acknowledged, accepted, declined, timed out, or escalated.

## Running the Backend Server

From the `backend/` directory:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` to view the interactive OpenAPI documentation.

## Running Automated Tests

From the `backend/` directory:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_incidents.py -v
```

