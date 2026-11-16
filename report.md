# AIoT Accident Detection and Alert System

## Executive summary

This repository contains a web application and FastAPI backend for vehicle telemetry, suspected accident detection, and hospital alert handling. Its intended flow is: a registered device reports motion/GPS data, the backend evaluates telemetry, a suspected incident enters a cancellation period, and—if not cancelled—an eligible hospital is notified and can respond.

The application has separate interfaces for hospital staff, superusers, and vehicle owners. Authentication and data storage rely on Supabase. This report describes the source and documentation present in this repository; it does not confirm a working deployment, validated crash-detection performance, or production readiness.

## Repository map

| Path | Purpose |
| --- | --- |
| `frontend/` | React/Vite single-page application and frontend documentation |
| `frontend/src/pages/auth/` | Login, authentication state, role guards, and auth rules |
| `frontend/src/pages/hospital/` | Hospital alert and incident workflows |
| `frontend/src/pages/superuser/` | Administrative dashboards and management workflows |
| `frontend/src/pages/vehicle/` | Vehicle-owner monitoring dashboard |
| `backend/app/main.py` | FastAPI app construction, middleware/CORS, and router registration |
| `backend/app/core/` | Configuration, database access, authentication, permissions, and device security |
| `backend/app/routers/` | HTTP and WebSocket API endpoints |
| `backend/app/schemas/` | Request/response validation models |
| `backend/app/services/` | Telemetry, incident, alert, inference, control, and WebSocket logic |
| `backend/app/workers/` | Incident deadline and escalation processing |
| `backend/tests/` | Backend workflow tests |
| `backend/models/accident_model.joblib` | Packaged inference model |
| `backend/postman/` | Postman collections for incident and hospital-alert APIs |

Root and module documentation includes setup and integration notes, a hospital dashboard README, an incident README, and an API/branch guide. The frontend also contains build output (`dist/` and `dist.zip`); these are artifacts rather than source. The ESP32 firmware source is not present in this repository.

## Technology

- **Frontend:** React 19, React Router, Vite, JavaScript/JSX, CSS, and the Supabase JavaScript client.
- **Backend:** Python and FastAPI, with Pydantic schemas and Supabase/Postgres access.
- **Authentication and persistence:** Supabase Auth and Postgres/PostgREST, including database RPC calls.
- **Device contract:** Authenticated HTTP reporting for device heartbeat, telemetry, and cancellation.
- **Model inference:** A checked-in `joblib` model bundle used by the backend telemetry pipeline.

## Application interfaces

### Authentication

The frontend login flow uses Supabase email/password sign-in, then obtains and verifies the user profile through the backend. Role-aware guards direct users to the hospital, superuser, or vehicle-owner areas. Backend permissions are the authoritative check for protected API actions.

### Hospital dashboard

Hospital pages provide an overview of assigned alerts, incident details, history/operations, location and health information, and reports. The UI supports alert acknowledgment, acceptance or decline, notes, false-alarm reporting, and incident closure. Reports can be exported as CSV. The alert feed currently refreshes through polling; the backend also defines a WebSocket endpoint.

### Superuser dashboard

Administrative pages cover overview, incidents, owners, vehicles, devices, hospitals, users, and audit/activity information. The UI uses administrative backend APIs to retrieve records and perform management actions. The corresponding backend routes require superuser permissions.

### Vehicle-owner dashboard

The vehicle area lists the owner's registered vehicles and displays status and recent uploaded motion data. It is a monitoring interface; the current dashboard does not issue driving commands.

## Backend architecture and workflows

`backend/app/main.py` constructs the FastAPI application and mounts authentication, admin, vehicle, device-reporting, device-state, incident, and alert routers. The code is organized by responsibility:

- **Routers** define the HTTP/WebSocket surface and apply authentication/authorization.
- **Schemas** validate API payloads such as devices, telemetry, incidents, and alerts.
- **Services** implement the core telemetry processing, inference, incident lifecycle, alert routing, and connection management.
- **Workers** process incident and hospital deadlines outside the normal request flow.
- **Core modules** provide configuration, Supabase access, user/device authentication, and permission checks.

### Device telemetry to incident

Device reporting endpoints accept heartbeats, telemetry, and device cancellation requests. Device requests use an `X-Device-Secret` credential checked against the registered device. Telemetry validation covers fields such as timestamps, units, GPS ranges, sample ordering, and expected sampling cadence. The processing service evaluates complete windows using the packaged model, stores prediction results, and calls a database RPC to create an incident when the result meets the suspected-crash condition.

### Incident and hospital response

Incident APIs expose authorized incident lists/details and actions such as cancellation, notes, false-alarm reporting, and closure. Hospital alert APIs support listing authorized alerts, acknowledgment, acceptance, decline, and administrative routing. The implementation describes a configurable cancellation window (30 seconds by default) before notification, followed by a configurable hospital acknowledgment deadline (180 seconds by default); decline or timeout can trigger escalation.

Deadline and escalation logic exists in `backend/app/workers/`. It requires an operational mechanism to run the workers; the FastAPI app setup does not itself start them.

## Data, configuration, and security

The backend uses Supabase Auth for human identities and Supabase/Postgres for application records. The code refers to records including profiles, devices, incidents, and audit logs, and calls database RPCs for parts of the workflow. No database migration or schema files were found in the repository. A deployment therefore depends on separately provisioned tables, functions, constraints, and access policies.

Human API requests use bearer tokens and backend-verified profile assignments. Device requests use a registered device secret. Owner, hospital, and superuser permissions are checked server-side. CORS configuration includes local development origins. Backend configuration examples are documented in `backend/.env.example`; secret values are intentionally not reproduced in this report.

## Device and live-control integration

The application documentation and vehicle UI refer to an ESP32/MPU6050 device, GPS, and a local vehicle Wi-Fi access point. The backend implements remote device reporting contracts, but no firmware source is checked into this repository.

The IDE-selected `AIoTCar-diagnostics.ino` is a separate sketch in the user's Downloads folder, not part of this repository. That sketch targets Arduino-ESP32 3.x and describes an ESP32 car with a local phone-control access point and a separate upstream connection for FastAPI reporting. It configures the MPU6050 hardware FIFO for 100 Hz sampling, groups 1,600 readings into telemetry windows, and attaches recent GPS fixes. When GPS is unavailable or stale, it can simulate a location within the configured bounded area, moving it based on motor commands; fresh real GPS fixes take precedence. It buffers windows in RAM, writes telemetry to a checksummed LittleFS outbox, verifies the saved file, and retries the same packet until the backend acknowledges it. Separate tasks handle sampling, uploads, heartbeat/incident-state polling, and motor safety. The sketch also includes a physical-button cancellation request during the incident cancellation window and extensive serial diagnostics.

The selected sketch includes `config.h`, `ControlLog.h`, and `LocalControl.h`; those companion files are not included in this repository. Thus its complete configuration and local controller implementation cannot be established from the checked-in project. Treat it as external firmware context rather than a buildable component of this repository.

Control-related code exists in the backend and frontend, but the control router is not mounted by the current FastAPI application entry point, and the vehicle-owner dashboard is monitoring-only. These code paths should not be assumed to be available as a deployed driving-control feature.

## Running and validating locally

### Frontend

From `frontend/`, install dependencies and use the scripts declared in `package.json`:

```powershell
npm install
npm run dev
npm run lint
npm run build
```

### Backend

From `backend/`, install the declared Python dependencies, configure environment variables using `.env.example`, and start the API:

```powershell
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

The backend test suite is under `backend/tests/`. Frontend test files exist for selected auth and superuser rules, but the frontend package manifest does not declare a test script. Tests/builds were not run while preparing this report.

## Scope and caveats

- Some root authentication documentation describes an earlier simulated or unprotected frontend; the current frontend source implements Supabase sign-in, profile verification, and role guards.
- The frontend Supabase client disables session persistence and signs out on page hide. Session continuity across browser refreshes should not be assumed without verifying the current behavior in the target environment.
- Database schema/RPC setup, worker scheduling, and firmware are external prerequisites or absent from this repository.
- A model score is not, on its own, evidence of a calibrated crash probability or validated safety/medical decision.
- Source inspection cannot confirm live credentials, database policies, device connectivity, alert delivery, or deployment behavior.
