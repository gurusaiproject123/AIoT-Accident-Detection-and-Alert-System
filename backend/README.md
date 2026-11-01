# AIoT Backend — Section 7: Hospital Alerts and Live Updates

**Branch:** `backend-hospital-alerts`  
**Lead:** Victor Gomwe

This module implements **Section 7 (Build hospital alerts and live updates)** from `AIoT_Backend_Branches_and_API_Guide.docx`. No database migrations were created or modified by this module.

---

## Implemented Endpoints & Live Channel

| Method | Endpoint | Access | Description |
| --- | --- | --- | --- |
| `GET` | `/api/hospital/alerts` | `hospital_staff` (verified hospital) | Lists notifications (`incident_notifications`) assigned to the caller's verified hospital. |
| `GET` | `/api/alerts/{id}` | Assigned `hospital_staff` or `superuser` | Returns one authorized notification (`incident_notifications` UUID) with incident/vehicle/owner context. |
| `POST` | `/api/alerts/{id}/acknowledge` | Assigned `hospital_staff` | Confirms receipt of a `notified` alert without automatically accepting the response. Clears the 180s ack countdown and broadcasts `alert.acknowledged`. |
| `POST` | `/api/alerts/{id}/accept` | Assigned `hospital_staff` | Records willingness to respond on an `acknowledged` alert, withdraws other open notifications, and broadcasts `alert.accepted`. |
| `POST` | `/api/alerts/{id}/decline` | Assigned `hospital_staff` | Requires a non-empty `reason` on an `acknowledged` alert, marks it `declined`, and escalates once to the next nearest eligible active hospital. |
| `POST` | `/api/admin/incidents/{id}/notify` | `superuser` | Manually routes an incident to a specified active hospital (`hospital_id` UUID). |
| `WS` | `/api/ws` | Authenticated `hospital_staff`, `superuser`, `car_owner` | Authenticated real-time channel. Scopes subscriptions from verified assignments (never broadcasts all incidents to all users). |

---

## Shared Service & Worker Contracts (Section 9)

- **`alert_service.route_incident(incident_id, ...)`** (`app/services/alert_service.py`):
  - Called after an uncancelled 30-second cancellation window expires, or when a hospital declines / times out.
  - Selects the nearest untried active hospital using Haversine distance on validated coordinates.
  - Sets a separate **180-second** acknowledgment deadline (`response_deadline`).
  - If coordinates are missing/invalid or no untried active hospital is available, records the unresolved routing state (`resolved=False`, `status="escalated"`) without inventing a destination.
- **`alert_service.set_incident_response_hook(...)`**:
  - Connects to `incident_service.apply_hospital_response(...)` when `backend-incidents` is merged.
- **`escalation_worker`** (`app/workers/escalation_worker.py`):
  - Evaluates stored 30-second cancellation deadlines and 180-second hospital acknowledgment deadlines, surviving worker restarts.

---

## Running the Backend & Tests

From the `backend/` directory:

```powershell
# Start the FastAPI server
python -m uvicorn app.main:app --reload

# Run the automated permission, workflow, escalation, and WebSocket tests
python -m unittest discover -s tests -p "test_*.py" -v
```

Interactive OpenAPI docs: `http://127.0.0.1:8000/docs`  
Postman collection: `backend/postman/AIoT_Backend_Hospital_Alerts.postman_collection.json`

