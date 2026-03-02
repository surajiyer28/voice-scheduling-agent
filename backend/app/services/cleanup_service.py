import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, delete

from app.database import AsyncSessionLocal
from app.models.booking import Booking
from app.models.host import Host
from app.services import calendar_service

logger = logging.getLogger(__name__)


async def run_cleanup_cycle() -> None:
    """Delete Google Calendar events and booking records for expired meetings."""
    async with AsyncSessionLocal() as db:
        try:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(Booking).where(
                    Booking.delete_at <= now,
                    Booking.calendar_event_id.isnot(None),
                    Booking.status == "confirmed",
                )
            )
            expired = result.scalars().all()

            for booking in expired:
                if booking.host_id and booking.calendar_event_id:
                    host_result = await db.execute(
                        select(Host).where(Host.id == booking.host_id)
                    )
                    host = host_result.scalar_one_or_none()
                    if host:
                        try:
                            await calendar_service.delete_event(
                                host, booking.calendar_event_id, db
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to delete GCal event {booking.calendar_event_id}: {e}"
                            )

            if expired:
                booking_ids = [b.id for b in expired]
                await db.execute(
                    delete(Booking).where(Booking.id.in_(booking_ids))
                )
                await db.commit()
                logger.info(f"Cleaned up {len(expired)} expired bookings")
        except Exception as e:
            logger.error(f"Cleanup cycle error: {e}")
            await db.rollback()


async def start_cleanup_loop() -> None:
    """Background task that runs cleanup every hour."""
    while True:
        try:
            await run_cleanup_cycle()
        except Exception as e:
            logger.error(f"Unexpected cleanup error: {e}")
        await asyncio.sleep(3600)
