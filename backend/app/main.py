from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.auth import router as auth_router
from app.routers.admin_hospitals import router as admin_hospitals_router
from app.routers.admin_users import router as admin_users_router
from app.routers.admin_audit import router as admin_audit_router
from app.routers.admin_overview import router as admin_overview_router
from app.routers.admin_incidents import router as admin_incidents_router
from app.routers.incidents import router as incidents_router


app = FastAPI(
    title="AIoT Accident Detection API",
    version="0.1.0",
)

# Allow requests from the local React frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Device-Secret"],
)

# Authentication and administration routes.
app.include_router(auth_router)
app.include_router(admin_hospitals_router)
app.include_router(admin_users_router)
app.include_router(admin_audit_router)
app.include_router(admin_overview_router)
app.include_router(admin_incidents_router)
app.include_router(incidents_router)


@app.get("/api/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
