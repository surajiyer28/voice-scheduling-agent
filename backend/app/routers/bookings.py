import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.host import Host
from app.models.booking import Booking
from app.schemas.booking import BookingResponse
from app.services import email_service, calendar_service
from app.services.booking_service import log_event
from app.auth import get_current_host

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


@router.get("", response_model=list[BookingResponse])
async def list_bookings(
    booking_status: Optional[str] = Query(None, alias="status"),
    from_dt: Optional[datetime] = Query(None, alias="from"),
    to_dt: Optional[datetime] = Query(None, alias="to"),
    current_host: Host = Depends(get_current_host),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Booking)
        .where(Booking.host_id == current_host.id)
        .order_by(Booking.start_time.asc())
    )
    if booking_status:
        query = query.where(Booking.status == booking_status)
    if from_dt:
        query = query.where(Booking.start_time >= from_dt)
    if to_dt:
        query = query.where(Booking.start_time <= to_dt)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: uuid.UUID,
    current_host: Host = Depends(get_current_host),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Booking).where(
            Booking.id == booking_id,
            Booking.host_id == current_host.id,
        )
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return booking


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_booking(
    booking_id: uuid.UUID,
    current_host: Host = Depends(get_current_host),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Booking).where(
            Booking.id == booking_id,
            Booking.host_id == current_host.id,
        )
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    booking.status = "cancelled"

    if booking.calendar_event_id:
        try:
            from app.services import calendar_service
            await calendar_service.delete_event(
                current_host, booking.calendar_event_id, db
            )
        except Exception:
            pass

    await log_event(
        event_type="booking_cancelled",
        db=db,
        booking_id=booking.id,
        details={"cancelled_by": "host"},
    )
    await db.commit()


@router.post("/{booking_id}/send-link", response_model=BookingResponse)
async def send_meeting_link(
    booking_id: uuid.UUID,
    current_host: Host = Depends(get_current_host),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Booking).where(
            Booking.id == booking_id,
            Booking.host_id == current_host.id,
        )
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if booking.status != "confirmed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking is not confirmed",
        )

    if not booking.calendar_event_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No calendar event associated with this booking",
        )

    # Auto-generate a Google Meet link on the calendar event
    meeting_link = await calendar_service.add_meet_link(
        current_host, booking.calendar_event_id, db
    )
    booking.meeting_link = meeting_link

    await email_service.send_meeting_link(
        host=current_host,
        caller_name=booking.caller_name,
        caller_email=booking.caller_email,
        meeting_link=meeting_link,
        start_time=booking.start_time,
        end_time=booking.end_time,
        title=booking.title,
        db=db,
    )
    booking.email_sent = True

    await log_event(
        event_type="link_sent",
        db=db,
        booking_id=booking.id,
        details={"meeting_link": meeting_link},
    )
    await db.commit()
    await db.refresh(booking)
    return booking
