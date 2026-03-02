from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from app.config import get_settings


def add_cors_middleware(app: FastAPI) -> None:
    settings = get_settings()
    origins = [settings.FRONTEND_URL, "http://localhost:3000"]
    origins = list(set(origins))

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
