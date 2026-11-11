from app.core.config import get_settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.alerts import router as alerts_router
from app.routers.auth import router as auth_router

from app.routers.admin_hospitals import router as admin_hospitals_router
from app.routers.admin_users import router as admin_users_router
from app.routers.admin_audit import router as admin_audit_router
from app.routers.admin_overview import router as admin_overview_router
from app.routers.admin_owners import router as admin_owners_router
from app.routers.admin_vehicles import router as admin_vehicles_router
from app.routers.admin_devices import router as admin_devices_router
from app.routers.admin_incidents import router as admin_incidents_router

from app.routers.vehicles import router as owner_vehicles_router
from app.routers.devices import router as device_reporting_router
from app.routers.incidents import router as incidents_router

from app.routers.control import router as control_router
from app.routers.device_state import router as device_state_router


app = FastAPI(
    title="AIoT Accident Detection API",
    description=(
        "Authentication, administration, vehicle registry, "
        "owner vehicle access, authenticated device reporting, "
        "live vehicle controls and incident management."
    ),
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Device-Secret",
    ],
)


# Authentication
app.include_router(auth_router)

# Administration
app.include_router(admin_hospitals_router)
app.include_router(admin_users_router)
app.include_router(admin_audit_router)
app.include_router(admin_overview_router)
app.include_router(admin_incidents_router)
app.include_router(admin_owners_router)
app.include_router(admin_vehicles_router)
app.include_router(admin_devices_router)

# Owner vehicle access
app.include_router(owner_vehicles_router)

# Device reporting and incident state
app.include_router(device_reporting_router)
app.include_router(device_state_router)

# Live driving controls and phone test page
app.include_router(control_router)

# Incidents and hospital alerts
app.include_router(incidents_router)
app.include_router(alerts_router)


@app.get("/api/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}