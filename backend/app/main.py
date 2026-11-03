from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.auth import router as auth_router
from app.routers.admin_hospitals import router as admin_hospitals_router
from app.routers.admin_users import router as admin_users_router


app = FastAPI(
    title="AIoT Accident Detection API",
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


@app.get("/api/health", tags=["Health"])
def health_check():
    return {"status": "ok"}