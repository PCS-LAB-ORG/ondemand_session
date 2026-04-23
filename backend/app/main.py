import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, sessions

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="On-Demand Session Manager",
    description="Manage per-user on-demand application sessions backed by Kubernetes pods",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(sessions.router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
