from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.host import Host
from app.models.availability import Availability
from app.schemas.host import HostResponse, HostUpdate, HostRegister
from app.auth import get_current_host

router = APIRouter(prefix="/api/hosts", tags=["hosts"])

DEFAULT_AVAILABILITY = [
    {"day_of_week": 0, "is_available": True},
    {"day_of_week": 1, "is_available": True},
    {"day_of_week": 2, "is_available": True},
    {"day_of_week": 3, "is_available": True},
    {"day_of_week": 4, "is_available": True},
    {"day_of_week": 5, "is_available": False},
    {"day_of_week": 6, "is_available": False},
]


@router.post("/register", response_model=HostResponse)
async def register_host(
    payload: HostRegister,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Host).where(Host.google_id == payload.google_id)
    )
    host = result.scalar_one_or_none()

    if host:
        host.email = payload.email
        host.name = payload.name
        host.picture = payload.picture
        if payload.access_token:
            host.google_access_token = payload.access_token
        if payload.refresh_token:
            host.google_refresh_token = payload.refresh_token
        if payload.token_expiry:
            host.google_token_expiry = payload.token_expiry
        await db.commit()
        await db.refresh(host)
        return host

    host = Host(
        google_id=payload.google_id,
        email=payload.email,
        name=payload.name,
        picture=payload.picture,
        google_access_token=payload.access_token,
        google_refresh_token=payload.refresh_token,
        google_token_expiry=payload.token_expiry,
    )
    db.add(host)
    await db.flush()
    await db.refresh(host)

    from datetime import time
    for slot in DEFAULT_AVAILABILITY:
        avail = Availability(
            host_id=host.id,
            day_of_week=slot["day_of_week"],
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_available=slot["is_available"],
        )
        db.add(avail)

    await db.commit()
    await db.refresh(host)
    return host


@router.get("/me", response_model=HostResponse)
async def get_me(
    current_host: Host = Depends(get_current_host),
):
    return current_host


@router.put("/me", response_model=HostResponse)
async def update_me(
    payload: HostUpdate,
    current_host: Host = Depends(get_current_host),
    db: AsyncSession = Depends(get_db),
):
    if payload.name is not None:
        current_host.name = payload.name
    if payload.picture is not None:
        current_host.picture = payload.picture
    if payload.timezone is not None:
        current_host.timezone = payload.timezone
    await db.commit()
    await db.refresh(current_host)
    return current_host
