from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.auth import router as auth_router
from app.routers.admin_hospitals import router as admin_hospitals_router
from app.routers.admin_users import router as admin_users_router
from app.routers.admin_audit import router as admin_audit_router
from app.routers.admin_overview import router as admin_overview_router
from app.routers.admin_owners import router as admin_owners_router
from app.routers.admin_vehicles import router as admin_vehicles_router
from app.routers.admin_devices import router as admin_devices_router
from app.routers.vehicles import router as owner_vehicles_router
from app.routers.devices import router as device_reporting_router


app = FastAPI(
    title="AIoT Accident Detection API",
    description=(
        "Authentication, administration, vehicle registry, "
        "owner vehicle access and authenticated device reporting."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router)

app.include_router(admin_hospitals_router)
app.include_router(admin_users_router)
app.include_router(admin_audit_router)
app.include_router(admin_overview_router)

app.include_router(admin_owners_router)
app.include_router(admin_vehicles_router)
app.include_router(admin_devices_router)

app.include_router(owner_vehicles_router)
app.include_router(device_reporting_router)


@app.get("/api/health", tags=["Health"])
def health_check():
    return {"status": "ok"}