from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from Api.auth import router as auth_router
from Api.datasets import router as datasets_router


app = FastAPI(
    title="DataFlow AI API",
    description="AI-powered analytics backend",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Routers
app.include_router(auth_router)
app.include_router(datasets_router)


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