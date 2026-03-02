import uuid
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.booking import Booking
from app.models.event_log import EventLog


def _sanitize_notes(notes: Optional[str]) -> Optional[str]:
    if notes is None:
        return None
    clean = re.sub(r"<[^>]+>", "", notes)
    return clean[:500]


async def check_slot_available(
    host_id: uuid.UUID,
    start_time: datetime,
    end_time: datetime,
    db: AsyncSession,
) -> bool:
    result = await db.execute(
        select(func.count(Booking.id)).where(
            Booking.host_id == host_id,
            Booking.status == "confirmed",
            Booking.start_time < end_time,
            Booking.end_time > start_time,
        )
    )
    return result.scalar_one() == 0


async def create_booking(
    host_id: uuid.UUID,
    caller_name: str,
    caller_email: str,
    title: str,
    notes: Optional[str],
    start_time: datetime,
    end_time: datetime,
    calendar_event_id: Optional[str],
    db: AsyncSession,
) -> Booking:
    booking = Booking(
        host_id=host_id,
        caller_name=caller_name,
        caller_email=caller_email,
        title=title or "Meeting",
        notes=_sanitize_notes(notes),
        start_time=start_time,
        end_time=end_time,
        calendar_event_id=calendar_event_id,
        status="confirmed",
        email_sent=False,
        delete_at=end_time + timedelta(hours=48),
    )
    db.add(booking)
    await db.flush()
    await db.refresh(booking)
    return booking


async def log_event(
    event_type: str,
    db: AsyncSession,
    booking_id: Optional[uuid.UUID] = None,
    details: Optional[dict] = None,
) -> None:
    entry = EventLog(
        booking_id=booking_id,
        event_type=event_type,
        details=details,
    )
    db.add(entry)
    await db.flush()
