from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.host import Host
from app.models.availability import Availability
from app.schemas.availability import AvailabilityResponse, AvailabilityUpdate
from app.auth import get_current_host

router = APIRouter(prefix="/api/availability", tags=["availability"])


@router.get("", response_model=list[AvailabilityResponse])
async def get_availability(
    current_host: Host = Depends(get_current_host),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Availability)
        .where(Availability.host_id == current_host.id)
        .order_by(Availability.day_of_week)
    )
    return result.scalars().all()


@router.put("", response_model=list[AvailabilityResponse])
async def update_availability(
    payload: AvailabilityUpdate,
    current_host: Host = Depends(get_current_host),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Availability).where(Availability.host_id == current_host.id)
    )
    existing = {a.day_of_week: a for a in result.scalars().all()}

    for slot in payload.slots:
        if slot.day_of_week in existing:
            avail = existing[slot.day_of_week]
            avail.start_time = slot.start_time
            avail.end_time = slot.end_time
            avail.is_available = slot.is_available
        else:
            avail = Availability(
                host_id=current_host.id,
                day_of_week=slot.day_of_week,
                start_time=slot.start_time,
                end_time=slot.end_time,
                is_available=slot.is_available,
            )
            db.add(avail)

    await db.commit()

    result = await db.execute(
        select(Availability)
        .where(Availability.host_id == current_host.id)
        .order_by(Availability.day_of_week)
    )
    return result.scalars().all()
