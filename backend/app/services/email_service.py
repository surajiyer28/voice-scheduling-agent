import base64
import logging
import uuid as _uuid
from datetime import datetime, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.host import Host
from app.services.calendar_service import get_credentials

logger = logging.getLogger(__name__)


def _format_datetime(dt: datetime, tz_name: str = "UTC") -> str:
    """Format a datetime for display in emails, converted to the given timezone."""
    local_dt = dt.astimezone(ZoneInfo(tz_name))
    hour = local_dt.hour % 12 or 12
    am_pm = "AM" if local_dt.hour < 12 else "PM"
    tz_abbr = local_dt.strftime("%Z")
    return f"{local_dt.strftime('%A, %B')} {local_dt.day}, {local_dt.year} at {hour}:{local_dt.strftime('%M')} {am_pm} {tz_abbr}"


async def send_booking_confirmation(
    host: Host,
    caller_name: str,
    caller_email: str,
    start_time: datetime,
    title: str,
    db: AsyncSession,
) -> None:
    """Send a booking confirmation email to the caller via the host's Gmail."""
    creds = await get_credentials(host, db)
    service = build("gmail", "v1", credentials=creds)

    formatted_time = _format_datetime(start_time, host.timezone)

    body_text = (
        f"Hi {caller_name},\n\n"
        f"Your meeting has been confirmed!\n\n"
        f"Details:\n"
        f"  - Meeting: {title}\n"
        f"  - With: {host.name}\n"
        f"  - When: {formatted_time}\n"
        f"  - Duration: 1 hour\n\n"
        f"You'll receive another email with the meeting link before your appointment.\n\n"
        f"If you need to make changes, please call us back.\n\n"
        f"Best regards,\n"
        f"{host.name}"
    )

    message = MIMEText(body_text)
    message["to"] = caller_email
    message["from"] = host.email
    message["subject"] = f"Booking Confirmed: {title} on {formatted_time}"

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    result = service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()

    logger.info(f"Confirmation email sent to {caller_email}, message ID: {result.get('id')}")


def _to_utc_str(dt: datetime) -> str:
    """Convert datetime to UTC iCalendar format: YYYYMMDDTHHMMSSZ."""
    utc_dt = dt.astimezone(timezone.utc) if dt.tzinfo else dt
    return utc_dt.strftime("%Y%m%dT%H%M%SZ")


def _generate_ics(
    title: str,
    start_time: datetime,
    end_time: datetime,
    location: str,
    organizer_email: str,
    organizer_name: str,
    attendee_email: str,
) -> str:
    """Generate an RFC 5545 VCALENDAR string for a meeting invite."""
    uid = f"{_uuid.uuid4()}@voiceagent"
    now_str = _to_utc_str(datetime.now(timezone.utc))
    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//VoiceSchedulingAgent//EN\r\n"
        "METHOD:REQUEST\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"DTSTAMP:{now_str}\r\n"
        f"DTSTART:{_to_utc_str(start_time)}\r\n"
        f"DTEND:{_to_utc_str(end_time)}\r\n"
        f"SUMMARY:{title}\r\n"
        f"LOCATION:{location}\r\n"
        f"ORGANIZER;CN={organizer_name}:mailto:{organizer_email}\r\n"
        f"ATTENDEE;RSVP=TRUE:mailto:{attendee_email}\r\n"
        "STATUS:CONFIRMED\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )


async def send_meeting_link(
    host: Host,
    caller_name: str,
    caller_email: str,
    meeting_link: str,
    start_time: datetime,
    end_time: datetime,
    title: str,
    db: AsyncSession,
) -> None:
    """Send a meeting link email with .ics calendar invite to the caller."""
    creds = await get_credentials(host, db)
    service = build("gmail", "v1", credentials=creds)

    formatted_time = _format_datetime(start_time, host.timezone)

    body_text = (
        f"Hi {caller_name},\n\n"
        f"Here's your meeting link for your upcoming appointment:\n\n"
        f"  Meeting: {title}\n"
        f"  When: {formatted_time}\n"
        f"  Link: {meeting_link}\n\n"
        f"A calendar invite is attached for your convenience.\n"
        f"Please join a few minutes early. See you there!\n\n"
        f"Best regards,\n"
        f"{host.name}"
    )

    message = MIMEMultipart("mixed")
    message["to"] = caller_email
    message["from"] = host.email
    message["subject"] = f"Meeting Link: Your appointment on {formatted_time}"
    message.attach(MIMEText(body_text, "plain"))

    ics_content = _generate_ics(
        title=title,
        start_time=start_time,
        end_time=end_time,
        location=meeting_link,
        organizer_email=host.email,
        organizer_name=host.name,
        attendee_email=caller_email,
    )
    ics_part = MIMEBase("text", "calendar", method="REQUEST")
    ics_part.set_payload(ics_content.encode("utf-8"))
    encoders.encode_base64(ics_part)
    ics_part.add_header("Content-Disposition", "attachment", filename="invite.ics")
    message.attach(ics_part)

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    result = service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()

    logger.info(f"Meeting link email sent to {caller_email}, message ID: {result.get('id')}")
