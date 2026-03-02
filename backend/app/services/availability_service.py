from datetime import datetime, timedelta, timezone, time as dt_time
from typing import Optional
from zoneinfo import ZoneInfo
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.host import Host
from app.models.booking import Booking
from app.models.availability import Availability
from app.services import calendar_service


def _ensure_utc(dt: datetime) -> datetime:
    """Return a timezone-aware datetime in UTC, coercing naive datetimes to UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def get_available_slots(
    host_id: uuid.UUID, date: datetime, host_timezone: str, db: AsyncSession
) -> list[dict]:
    """
    Given a date (interpreted in the host's timezone), return up to 5 free
    1-hour slots within the host's availability window for that day.
    Slots are returned in the host's local timezone.
    DB queries use UTC.
    """
    host_tz = ZoneInfo(host_timezone)

    # Interpret the incoming date as a date in the host's timezone
    local_date = date.date() if hasattr(date, 'date') else date
    day_of_week = local_date.weekday()

    avail_result = await db.execute(
        select(Availability).where(
            Availability.host_id == host_id,
            Availability.day_of_week == day_of_week,
            Availability.is_available == True,
        )
    )
    avail = avail_result.scalar_one_or_none()
    if not avail:
        return []

    # Build start/end in host-local time, then convert to UTC for DB queries
    base_local = datetime.combine(local_date, avail.start_time, tzinfo=host_tz)
    window_end_local = datetime.combine(local_date, avail.end_time, tzinfo=host_tz)

    base_utc = base_local.astimezone(timezone.utc)
    window_end_utc = window_end_local.astimezone(timezone.utc)

    # Use proper overlap detection
    bookings_result = await db.execute(
        select(Booking).where(
            Booking.host_id == host_id,
            Booking.status == "confirmed",
            Booking.start_time < window_end_utc,
            Booking.end_time > base_utc,
        )
    )
    existing = bookings_result.scalars().all()
    booked_ranges = [
        (_ensure_utc(b.start_time), _ensure_utc(b.end_time)) for b in existing
    ]

    slots = []
    current_utc = base_utc
    while current_utc + timedelta(hours=1) <= window_end_utc and len(slots) < 5:
        slot_end_utc = current_utc + timedelta(hours=1)
        overlap = any(
            not (slot_end_utc <= bs or current_utc >= be) for bs, be in booked_ranges
        )
        if not overlap:
            # Convert back to host-local time for display
            slot_start_local = current_utc.astimezone(host_tz)
            slot_end_local = slot_end_utc.astimezone(host_tz)
            slots.append({
                "start": slot_start_local.isoformat(),
                "end": slot_end_local.isoformat(),
            })
        current_utc += timedelta(hours=1)

    return slots


async def find_best_host(
    requested_start: datetime,
    requested_end: datetime,
    db: AsyncSession,
) -> Optional[Host]:
    """
    Check all active hosts and return the one with fewest bookings that day
    who is free at the requested time per both DB and Google Calendar checks.
    requested_start/requested_end arrive as UTC (ISO 8601 with offset).
    For each host, we convert to their local time to check availability windows.
    """
    requested_start = _ensure_utc(requested_start)
    requested_end = _ensure_utc(requested_end)

    hosts_result = await db.execute(
        select(Host).where(Host.is_active == True)
    )
    all_hosts = hosts_result.scalars().all()

    candidates = []
    for host in all_hosts:
        host_tz = ZoneInfo(host.timezone)

        # Convert requested times to host-local for availability window check
        local_start = requested_start.astimezone(host_tz)
        local_end = requested_end.astimezone(host_tz)

        day_of_week = local_start.weekday()
        req_time = local_start.time()
        req_end_time = local_end.time()

        avail_result = await db.execute(
            select(Availability).where(
                Availability.host_id == host.id,
                Availability.day_of_week == day_of_week,
                Availability.is_available == True,
            )
        )
        avail = avail_result.scalar_one_or_none()
        if not avail:
            continue

        if req_time < avail.start_time or req_end_time > avail.end_time:
            continue

        # Check no confirmed booking overlaps the requested slot (in UTC)
        overlap_result = await db.execute(
            select(func.count(Booking.id)).where(
                Booking.host_id == host.id,
                Booking.status == "confirmed",
                Booking.start_time < requested_end,
                Booking.end_time > requested_start,
            )
        )
        overlap_count = overlap_result.scalar_one()
        if overlap_count > 0:
            continue

        try:
            is_free = await calendar_service.check_free_busy(
                host, requested_start, requested_end, db
            )
            if not is_free:
                continue
        except Exception:
            continue

        # Count how many bookings this host already has today (in UTC)
        day_start = requested_start.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = requested_start.replace(hour=23, minute=59, second=59, microsecond=999999)
        day_bookings_result = await db.execute(
            select(func.count(Booking.id)).where(
                Booking.host_id == host.id,
                Booking.status == "confirmed",
                Booking.start_time >= day_start,
                Booking.start_time <= day_end,
            )
        )
        day_count = day_bookings_result.scalar_one()
        candidates.append((day_count, host))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]
