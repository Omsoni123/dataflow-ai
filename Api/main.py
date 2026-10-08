import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from Api.auth import router as auth_router
from Api.datasets import router as datasets_router
from Api.billing import router as billing_router


app = FastAPI(
    title="DataFlow AI API",
    description="AI-powered analytics backend",
    version="1.0.0",
)


# ==========================================================
# CORS
# ==========================================================

frontend_url = os.getenv(
    "FRONTEND_URL",
    "http://localhost:3000",
)

allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    frontend_url,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(set(allowed_origins)),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================================
# ROUTERS
# ==========================================================

app.include_router(auth_router)
app.include_router(datasets_router)
app.include_router(billing_router)

# ==========================================================
# HEALTH CHECK
# ==========================================================

@app.get("/")
def root():
    return {
        "status": "online",
        "message": "DataFlow AI API is running",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }