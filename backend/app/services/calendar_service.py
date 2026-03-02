from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo
import uuid

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from app.config import get_settings
from app.models.host import Host

settings = get_settings()

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.send",
]


async def get_credentials(host: Host, db: AsyncSession) -> Credentials:
    creds = Credentials(
        token=host.google_access_token,
        refresh_token=host.google_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )

    if host.google_token_expiry:
        expiry = host.google_token_expiry
        # google-auth internally compares expiry against utcnow() (naive),
        # so creds.expiry must be a naive UTC datetime.
        if expiry.tzinfo is not None:
            expiry = expiry.astimezone(timezone.utc).replace(tzinfo=None)
        creds.expiry = expiry

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        await db.execute(
            update(Host)
            .where(Host.id == host.id)
            .values(
                google_access_token=creds.token,
                google_token_expiry=creds.expiry,
            )
        )
        await db.commit()

    return creds


async def check_free_busy(
    host: Host, start_time: datetime, end_time: datetime, db: AsyncSession
) -> bool:
    """Returns True if the host is free in the given window."""
    creds = await get_credentials(host, db)
    service = build("calendar", "v3", credentials=creds)

    start_iso = start_time.astimezone(timezone.utc).isoformat()
    end_iso = end_time.astimezone(timezone.utc).isoformat()

    body = {
        "timeMin": start_iso,
        "timeMax": end_iso,
        "items": [{"id": host.calendar_id or "primary"}],
    }

    result = service.freebusy().query(body=body).execute()
    busy_slots = result.get("calendars", {}).get(
        host.calendar_id or "primary", {}
    ).get("busy", [])

    return len(busy_slots) == 0


async def create_event(
    host: Host,
    title: str,
    start_time: datetime,
    end_time: datetime,
    notes: Optional[str],
    caller_name: str,
    db: AsyncSession,
) -> str:
    """Creates a calendar event and returns the event ID."""
    creds = await get_credentials(host, db)
    service = build("calendar", "v3", credentials=creds)

    description_parts = [
        "Scheduled via Voice Agent",
        f"Caller: {caller_name}",
    ]
    if notes:
        description_parts.append(notes)
    description_parts.append(
        "A meeting link will be shared with you shortly before the call."
    )

    host_tz_name = host.timezone if host.timezone else "America/New_York"
    host_tz = ZoneInfo(host_tz_name)

    # Convert to host-local time so Google Calendar renders it correctly
    start_local = start_time.astimezone(host_tz)
    end_local = end_time.astimezone(host_tz)

    event_body = {
        "summary": title,
        "description": "\n".join(description_parts),
        "start": {
            "dateTime": start_local.isoformat(),
            "timeZone": host_tz_name,
        },
        "end": {
            "dateTime": end_local.isoformat(),
            "timeZone": host_tz_name,
        },
    }

    event = (
        service.events()
        .insert(calendarId=host.calendar_id or "primary", body=event_body)
        .execute()
    )
    return event["id"]


async def delete_event(
    host: Host, calendar_event_id: str, db: AsyncSession
) -> None:
    """Deletes a calendar event. Silently handles 404 (already deleted)."""
    try:
        creds = await get_credentials(host, db)
        service = build("calendar", "v3", credentials=creds)
        service.events().delete(
            calendarId=host.calendar_id or "primary",
            eventId=calendar_event_id,
        ).execute()
    except HttpError as e:
        if e.resp.status == 404:
            return
        raise


async def update_event(
    host: Host, calendar_event_id: str, updates: dict, db: AsyncSession
) -> None:
    """Updates a calendar event with the given fields. Silently handles 404."""
    try:
        creds = await get_credentials(host, db)
        service = build("calendar", "v3", credentials=creds)
        service.events().patch(
            calendarId=host.calendar_id or "primary",
            eventId=calendar_event_id,
            body=updates,
        ).execute()
    except HttpError as e:
        if e.resp.status == 404:
            return
        raise


async def add_meet_link(
    host: Host, calendar_event_id: str, db: AsyncSession
) -> str:
    """Add a Google Meet conference to an existing event. Returns the Meet URL."""
    creds = await get_credentials(host, db)
    service = build("calendar", "v3", credentials=creds)

    event = service.events().patch(
        calendarId=host.calendar_id or "primary",
        eventId=calendar_event_id,
        body={
            "conferenceData": {
                "createRequest": {
                    "requestId": str(uuid.uuid4()),
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            }
        },
        conferenceDataVersion=1,
    ).execute()

    entry_points = (
        event.get("conferenceData", {}).get("entryPoints", [])
    )
    for ep in entry_points:
        if ep.get("entryPointType") == "video":
            return ep["uri"]

    raise RuntimeError("Google Meet link was not created")
