import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.middleware.cors import add_cors_middleware
from app.routers import health, hosts, availability, bookings, vapi_webhook
from app.services.cleanup_service import start_cleanup_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

_cleanup_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _cleanup_task
    _cleanup_task = asyncio.create_task(start_cleanup_loop())
    logger.info("Background cleanup task started")
    yield
    if _cleanup_task:
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass
    logger.info("Background cleanup task stopped")


app = FastAPI(
    title="Voice Scheduling Agent API",
    version="1.0.0",
    lifespan=lifespan,
)

add_cors_middleware(app)

app.include_router(health.router)
app.include_router(hosts.router)
app.include_router(availability.router)
app.include_router(bookings.router)
app.include_router(vapi_webhook.router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred.", "status_code": 500},
    )
