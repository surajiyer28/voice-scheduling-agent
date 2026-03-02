import json
import uuid
import logging
import httpx
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.schemas.vapi import (
    VapiWebhookPayload,
    VapiResponse,
    VapiToolResult,
    CheckAvailabilityArgs,
    CreateBookingArgs,
    LogCallEventArgs,
)
from app.services import availability_service, calendar_service, email_service
from app.services.booking_service import (
    check_slot_available,
    create_booking,
    log_event,
)

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vapi", tags=["vapi"])

# Cached VAPI assistant ID — created once per process lifetime.
_vapi_assistant_id: str | None = None


def _build_system_prompt(today_str: str) -> str:
    return f"""You are a friendly, professional scheduling assistant. Your only job is to help callers book a 1-hour meeting.

Today is {today_str}. Use this to resolve relative date expressions like "tomorrow", "next Monday", "this Friday" into exact YYYY-MM-DD dates. Always derive the correct day name from the computed date — never guess.

CONVERSATION FLOW — follow this exact order on every call:

STEP 1 — Get the caller's name.
Ask: "May I have your name please?"

STEP 2 — Get their preferred date.
Ask what date works for them. Accept any natural phrasing.
- Internally compute the exact calendar date (YYYY-MM-DD).
- Confirm it with the full day name: "Just to confirm — that would be [Day Name], [Month] [Day], [Year]? Is that right?"
- Wait for an explicit yes before continuing. If they say no, ask again.

STEP 3 — Check availability.
You MUST call the check_availability tool. NEVER fabricate or guess available times.
Say "Let me see what times are available" and then immediately call check_availability with the confirmed date (YYYY-MM-DD).
Once the tool returns, IMMEDIATELY read out the results to the caller — do not wait for them to ask.

STEP 4 — Present available times.
As soon as you receive the check_availability result, read out the times right away.
Do NOT mention any host names at this stage.
IMPORTANT: The check_availability result includes a "timezone_label" field (e.g. "Eastern", "Pacific"). Always include this timezone label when reading times aloud.
Example: "Great news! I have openings at 9 AM, 10 AM, and 2 PM Eastern. Which time works best for you?"
- If no slots: "I'm sorry, there's nothing available that day. Would you like to try a different date?"

STEP 5 — Confirm the chosen time.
Once they choose, say: "Perfect, [time] it is."

STEP 6 — Ask for the meeting purpose.
Ask: "What would you like the purpose of this meeting to be?"
Listen and acknowledge their answer.

STEP 7 — Get and confirm their email address.
Ask: "What's the best email address to send the booking confirmation to?"
After they provide it, spell it back CHARACTER BY CHARACTER to confirm:
- Say each letter individually using the letter itself (e.g. "s, u, r, a, j")
- Say numbers as digits: "two, eight" (NOT "twenty-eight")
- Say "at" for the @ symbol
- Say "dot" for periods
- Pause briefly between each character so it's clear
Example for "surajiyer28.si@gmail.com":
"Let me spell that back: s, u, r, a, j, i, y, e, r, two, eight, dot, s, i, at, g, m, a, i, l, dot, c, o, m — is that correct?"
Wait for confirmation. If they correct any part, spell the full corrected email back again before continuing.

STEP 8 — Create the booking.
You MUST call the create_booking tool. NEVER pretend a booking was made without calling the tool.
Say "Let me get that booked for you now" and then immediately call create_booking with:
- host_id: the UUID from the slot the caller chose in step 4 (each slot in check_availability has a host_id)
- caller_name: from step 1
- caller_email: the confirmed email address from step 7
- start_time: copy the EXACT "start" string from the chosen check_availability slot (e.g. "2026-03-05T14:00:00-05:00"). Do NOT modify the timezone offset — use the value exactly as returned.
- end_time: copy the EXACT "end" string from the chosen check_availability slot. Do NOT modify the timezone offset.
- title: the meeting purpose from step 6

STEP 9 — Confirm success.
As soon as create_booking returns successfully, IMMEDIATELY tell the caller the result — do not wait for them to ask.
Say: "You're all set! You've been booked with [host_name from the booking result] on [Day Name], [Month] [Day] at [time] [timezone label from step 4] for [purpose]. An email confirmation is on its way to [email]. Have a great day!"
Then call log_call_event with event_type "booking_confirmed".

STEP 10 — Handle failure.
If create_booking returns an error, say: "I'm sorry, I ran into a technical issue on my end. Please call back and we'll get that sorted out. I apologize for the inconvenience."
Call log_call_event with event_type "booking_failed" and end the call.

CRITICAL RULES — never break these:
- NEVER ask who the caller wants to meet with. Host assignment is automatic — you don't ask about it.
- NEVER mention a host name until AFTER a successful booking in step 9.
- NEVER ask callers to say dates in any specific format — always accept natural language.
- NEVER guess or assume availability — you MUST call check_availability and use only the data it returns. Making up times is absolutely forbidden.
- NEVER pretend a booking was created — you MUST call create_booking and use only its actual result.
- NEVER reveal JSON, UUIDs, parameter names, or tool names to the caller.
- ALWAYS confirm the resolved date with the correct day name before checking availability.
- ALWAYS repeat the email address back before creating the booking.
- ALWAYS use the host_id from the specific slot the caller chose, not from a different slot.
- ALWAYS announce results to the caller IMMEDIATELY after receiving a tool response. Never go silent or wait for the caller to ask "did it work?" or "what happened?" — tell them right away.
- Use natural, warm phrasing. Never say "hold on a sec" — say "Let me check that for you" or "Let me get that sorted."
- Be concise. Don't over-explain."""


async def _get_or_create_vapi_assistant() -> str:
    """
    Return the cached VAPI assistant ID, creating it via the VAPI REST API if
    it doesn't exist yet.
    """
    global _vapi_assistant_id
    if _vapi_assistant_id:
        return _vapi_assistant_id

    base_url = settings.BACKEND_URL
    webhook_url = f"{base_url}/api/vapi/webhook"
    tool_server = {"url": webhook_url, "secret": settings.VAPI_WEBHOOK_SECRET}

    assistant_payload = {
        "name": "Voice Scheduling Agent",
        "firstMessage": "Hello! I'm your scheduling assistant. I can help you to schedule a meeting. May I start with your name please?",
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "en",
        },
        "model": {
            "provider": "openai",
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "system",
                    "content": _build_system_prompt("{{today}}"),
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "check_availability",
                        "description": (
                            "Check available 1-hour appointment slots on a given date. "
                            "Returns a list of slots, each with start, end, host_id, and host_name. "
                            "The host is selected automatically — do not ask the caller about it."
                        ),
                        "parameters": {
                            "type": "object",
                            "required": ["date"],
                            "properties": {
                                "date": {
                                    "type": "string",
                                    "description": "Date in YYYY-MM-DD format (e.g. 2026-03-05)",
                                },
                            },
                        },
                    },
                    "server": tool_server,
                },
                {
                    "type": "function",
                    "function": {
                        "name": "create_booking",
                        "description": "Create a confirmed 1-hour booking for a caller.",
                        "parameters": {
                            "type": "object",
                            "required": ["caller_name", "caller_email", "host_id", "start_time", "end_time"],
                            "properties": {
                                "caller_name": {
                                    "type": "string",
                                    "description": "Full name of the caller",
                                },
                                "caller_email": {
                                    "type": "string",
                                    "description": "Caller's email address for booking confirmation",
                                },
                                "host_id": {
                                    "type": "string",
                                    "description": "Host UUID taken from the chosen slot returned by check_availability",
                                },
                                "start_time": {
                                    "type": "string",
                                    "description": "Exact 'start' value from the chosen check_availability slot. Do not modify.",
                                },
                                "end_time": {
                                    "type": "string",
                                    "description": "Exact 'end' value from the chosen check_availability slot. Do not modify.",
                                },
                                "title": {
                                    "type": "string",
                                    "description": "Purpose or title of the meeting as stated by the caller",
                                },
                            },
                        },
                    },
                    "server": tool_server,
                },
                {
                    "type": "function",
                    "function": {
                        "name": "log_call_event",
                        "description": "Log a call event for auditing purposes.",
                        "parameters": {
                            "type": "object",
                            "required": ["event_type"],
                            "properties": {
                                "event_type": {
                                    "type": "string",
                                    "description": "Event type, e.g. booking_confirmed, booking_failed",
                                },
                                "booking_id": {
                                    "type": "string",
                                    "description": "Booking UUID if applicable",
                                },
                            },
                        },
                    },
                    "server": tool_server,
                },
            ],
        },
        "voice": {
            "provider": "11labs",
            "voiceId": "sarah",
            "model": "eleven_turbo_v2_5",
            "stability": 0.5,
            "similarityBoost": 0.75,
        },
        "backgroundDenoisingEnabled": True,
        "server": {
            "url": webhook_url,
            "secret": settings.VAPI_WEBHOOK_SECRET,
        },
        "serverMessages": ["tool-calls", "end-of-call-report"],
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.vapi.ai/assistant",
            json=assistant_payload,
            headers={
                "Authorization": f"Bearer {settings.VAPI_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=15.0,
        )
        if not resp.is_success:
            logger.error(
                f"VAPI assistant creation failed: {resp.status_code} — {resp.text}"
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Could not create VAPI assistant: {resp.status_code}",
            )
        data = resp.json()
        _vapi_assistant_id = data["id"]
        logger.info(f"Created VAPI assistant: {_vapi_assistant_id}")

    return _vapi_assistant_id


def _build_assistant_response() -> dict:
    """
    Return the full inline assistant config for assistant-request.
    """
    now = datetime.now(timezone.utc)
    today_str = (
        f"{now.strftime('%A')}, {now.strftime('%B')} {now.day}, {now.year}"
    )
    base_url = settings.BACKEND_URL
    webhook_url = f"{base_url}/api/vapi/webhook"
    tool_server = {"url": webhook_url, "secret": settings.VAPI_WEBHOOK_SECRET}

    return {
        "assistant": {
            "name": "Voice Scheduling Agent",
            "firstMessage": "Hello! I'm your scheduling assistant. I can help you book a 1-hour meeting. May I start with your name please?",
            "transcriber": {
                "provider": "deepgram",
                "model": "nova-2",
                "language": "en",
            },
            "model": {
                "provider": "openai",
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "system",
                        "content": _build_system_prompt(today_str),
                    }
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "check_availability",
                            "description": (
                                "Check available 1-hour appointment slots on a given date. "
                                "Returns a list of slots, each with start, end, host_id, and host_name. "
                                "The host is selected automatically — do not ask the caller about it."
                            ),
                            "parameters": {
                                "type": "object",
                                "required": ["date"],
                                "properties": {
                                    "date": {
                                        "type": "string",
                                        "description": "Date in YYYY-MM-DD format (e.g. 2026-03-05)",
                                    },
                                },
                            },
                        },
                        "server": tool_server,
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "create_booking",
                            "description": "Create a confirmed 1-hour booking for a caller.",
                            "parameters": {
                                "type": "object",
                                "required": ["caller_name", "caller_email", "host_id", "start_time", "end_time"],
                                "properties": {
                                    "caller_name": {"type": "string", "description": "Full name of the caller"},
                                    "caller_email": {"type": "string", "description": "Caller's email address for booking confirmation"},
                                    "host_id": {"type": "string", "description": "Host UUID from the chosen slot returned by check_availability"},
                                    "start_time": {"type": "string", "description": "Exact 'start' value from the chosen check_availability slot. Do not modify."},
                                    "end_time": {"type": "string", "description": "Exact 'end' value from the chosen check_availability slot. Do not modify."},
                                    "title": {"type": "string", "description": "Purpose of the meeting as stated by the caller"},
                                },
                            },
                        },
                        "server": tool_server,
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "log_call_event",
                            "description": "Log a call event for auditing.",
                            "parameters": {
                                "type": "object",
                                "required": ["event_type"],
                                "properties": {
                                    "event_type": {"type": "string"},
                                    "booking_id": {"type": "string"},
                                },
                            },
                        },
                        "server": tool_server,
                    },
                ],
            },
            "voice": {
                "provider": "11labs",
                "voiceId": "sarah",
                "model": "eleven_turbo_v2_5",
                "stability": 0.5,
                "similarityBoost": 0.75,
            },
            "backgroundDenoisingEnabled": True,
            "server": {
                "url": webhook_url,
                "secret": settings.VAPI_WEBHOOK_SECRET,
            },
            "serverMessages": ["tool-calls", "end-of-call-report"],
        }
    }


def _validate_vapi_secret(request: Request) -> None:
    secret = request.headers.get("x-vapi-secret", "")
    if secret != settings.VAPI_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid VAPI webhook secret",
        )


def _parse_datetime(dt_str: str) -> datetime:
    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


async def _resolve_host(host_id_or_name: str | None, db: AsyncSession):
    """Resolve a host UUID string or name to a Host model, or return None."""
    from app.models.host import Host as HostModel
    from sqlalchemy import select, func

    if not host_id_or_name:
        return None

    try:
        host_uuid = uuid.UUID(host_id_or_name)
        result = await db.execute(select(HostModel).where(HostModel.id == host_uuid))
        return result.scalar_one_or_none()
    except (ValueError, AttributeError):
        pass

    result = await db.execute(
        select(HostModel).where(
            func.lower(HostModel.name).contains(host_id_or_name.lower()),
            HostModel.is_active == True,
        )
    )
    return result.scalars().first()


_TIMEZONE_LABELS = {
    "America/New_York": "Eastern",
    "America/Chicago": "Central",
    "America/Denver": "Mountain",
    "America/Los_Angeles": "Pacific",
    "America/Anchorage": "Alaska",
    "America/Honolulu": "Hawaii",
}


async def _handle_check_availability(
    args: dict[str, Any], db: AsyncSession
) -> dict:
    from app.models.host import Host as HostModel
    from sqlalchemy import select

    parsed = CheckAvailabilityArgs(**args)

    try:
        date_obj = datetime.strptime(parsed.date, "%Y-%m-%d")
    except ValueError:
        return {"error": f"Invalid date format: {parsed.date}. Use YYYY-MM-DD."}

    hosts_result = await db.execute(
        select(HostModel).where(HostModel.is_active == True)
    )
    all_hosts = hosts_result.scalars().all()

    all_slots: list[dict] = []
    first_timezone: str | None = None
    for h in all_hosts:
        if first_timezone is None:
            first_timezone = h.timezone
        slots = await availability_service.get_available_slots(
            h.id, date_obj, h.timezone, db
        )
        for s in slots:
            s["host_id"] = str(h.id)
            s["host_name"] = h.name
        all_slots.extend(slots)

    seen_starts: set[str] = set()
    unique_slots: list[dict] = []
    for slot in sorted(all_slots, key=lambda x: x["start"]):
        if slot["start"] not in seen_starts:
            seen_starts.add(slot["start"])
            unique_slots.append(slot)

    timezone_label = _TIMEZONE_LABELS.get(first_timezone or "", first_timezone or "UTC")

    if unique_slots:
        return {"available": True, "slots": unique_slots[:5], "timezone_label": timezone_label}

    return {"available": False, "reason": f"No availability on {parsed.date}. Please try a different date."}


async def _handle_create_booking(
    args: dict[str, Any], db: AsyncSession
) -> dict:
    parsed = CreateBookingArgs(**args)

    try:
        start_time = _parse_datetime(parsed.start_time)
        end_time = _parse_datetime(parsed.end_time)
    except (ValueError, AttributeError) as e:
        return {"success": False, "error": f"Invalid datetime: {e}"}

    host = await _resolve_host(parsed.host_id, db)
    if not host:
        return {"success": False, "error": f"Host not found: {parsed.host_id}"}
    host_id = host.id

    still_free = await check_slot_available(host_id, start_time, end_time, db)
    if not still_free:
        return {"success": False, "error": "slot_taken"}

    calendar_event_id: str | None = None
    if host.google_access_token:
        try:
            calendar_event_id = await calendar_service.create_event(
                host=host,
                title=parsed.title or "Meeting",
                start_time=start_time,
                end_time=end_time,
                notes=parsed.notes,
                caller_name=parsed.caller_name,
                db=db,
            )
        except Exception as e:
            logger.warning(f"Calendar create_event failed (non-fatal): {e}")
    else:
        logger.info(f"Host {host.name} has no Google token — skipping calendar event")

    booking = await create_booking(
        host_id=host_id,
        caller_name=parsed.caller_name,
        caller_email=parsed.caller_email,
        title=parsed.title or "Meeting",
        notes=parsed.notes,
        start_time=start_time,
        end_time=end_time,
        calendar_event_id=calendar_event_id,
        db=db,
    )

    try:
        await email_service.send_booking_confirmation(
            host=host,
            caller_name=parsed.caller_name,
            caller_email=parsed.caller_email,
            start_time=start_time,
            title=parsed.title or "Meeting",
            db=db,
        )
        booking.email_sent = True
    except Exception as e:
        logger.error(f"Email send failed: {e}")

    await log_event(
        event_type="booking_created",
        db=db,
        booking_id=booking.id,
        details={
            "caller_name": parsed.caller_name,
            "host_id": str(host_id),
            "start_time": start_time.isoformat(),
        },
    )

    if booking.email_sent:
        await log_event(event_type="email_sent", db=db, booking_id=booking.id)

    await db.commit()

    return {
        "success": True,
        "booking_id": str(booking.id),
        "host_name": host.name,
        "calendar_event_id": calendar_event_id,
    }


async def _handle_log_call_event(
    args: dict[str, Any], db: AsyncSession
) -> dict:
    parsed = LogCallEventArgs(**args)
    booking_id: uuid.UUID | None = None
    if parsed.booking_id:
        try:
            booking_id = uuid.UUID(parsed.booking_id)
        except ValueError:
            pass

    await log_event(
        event_type=parsed.event_type,
        db=db,
        booking_id=booking_id,
        details=parsed.details,
    )
    await db.commit()
    return {"logged": True}


@router.post("/webhook")
async def vapi_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    msg = body.get("message", {})
    msg_type = msg.get("type", "")
    logger.info(f"VAPI webhook [{msg_type}] received")
    if msg_type == "tool-calls":
        logger.info(f"Raw tool-calls payload: {json.dumps(msg, default=str)[:2000]}")

    # assistant-request: fired by the phone number before the assistant is known.
    if msg_type == "assistant-request":
        logger.info("Returning inline assistant config")
        return _build_assistant_response()

    if msg_type == "tool-calls":
        _validate_vapi_secret(request)

        raw_with_list = msg.get("toolWithToolCallList") or []
        raw_call_list = msg.get("toolCallList") or msg.get("toolCalls") or []

        # Normalise into a uniform list of (tool_call_id, tool_name, args)
        calls: list[tuple[str, str, dict]] = []
        for item in raw_with_list:
            tc = item.get("toolCall", {})
            tc_fn = tc.get("function", {})
            item_fn = item.get("function", {})
            name = item_fn.get("name") or tc_fn.get("name") or item.get("name") or tc.get("name", "")
            call_id = tc.get("id", "unknown")
            params = tc_fn.get("arguments") or tc.get("parameters") or {}
            if isinstance(params, str):
                try:
                    params = json.loads(params)
                except Exception:
                    params = {}
            calls.append((call_id, name, params))

        if not calls:
            for tc in raw_call_list:
                tc_fn = tc.get("function", {})
                name = tc.get("name") or tc_fn.get("name", "")
                params = tc.get("parameters") or tc_fn.get("arguments") or {}
                if isinstance(params, str):
                    try:
                        params = json.loads(params)
                    except Exception:
                        params = {}
                call_id = tc.get("id", "unknown")
                calls.append((call_id, name, params))

        logger.info(f"Processing {len(calls)} tool call(s)")
        results = []
        for tool_call_id, tool_name, args in calls:
            logger.info(f"Tool call: {tool_name} args={args}")
            try:
                if tool_name == "check_availability":
                    result_data = await _handle_check_availability(args, db)
                elif tool_name == "create_booking":
                    result_data = await _handle_create_booking(args, db)
                elif tool_name == "log_call_event":
                    result_data = await _handle_log_call_event(args, db)
                else:
                    result_data = {"error": f"Unknown tool: {tool_name}"}
            except Exception as e:
                logger.exception(f"Tool call error [{tool_name}]: {e}")
                result_data = {"error": str(e)}
            # VAPI requires result to be a string, not an object
            result_str = json.dumps(result_data)
            logger.info(f"Tool result [{tool_name}]: {result_str[:500]}")
            results.append({
                "toolCallId": tool_call_id,
                "name": tool_name,
                "result": result_str,
            })
        return {"results": results}

    # All other event types (status-update, speech-update, end-of-call-report, etc.)
    return {"received": True}


# ---------------------------------------------------------------------------
# Individual tool endpoints — kept for backward compat / direct testing.
# ---------------------------------------------------------------------------

async def _handle_tool_request(
    tool_name: str,
    request: Request,
    db: AsyncSession,
) -> dict:
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    logger.info(f"VAPI tool call [{tool_name}]: {body}")

    try:
        msg = body.get("message", {})
        tool_calls = msg.get("toolCallList") or msg.get("toolCalls") or []
        if tool_calls:
            args = tool_calls[0].get("function", {}).get("arguments", {})
            tool_call_id = tool_calls[0].get("id", "unknown")
        else:
            args = body
            tool_call_id = body.get("id", "unknown")
    except Exception:
        args = body
        tool_call_id = "unknown"

    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {}

    if tool_name == "check_availability":
        result_data = await _handle_check_availability(args, db)
    elif tool_name == "create_booking":
        result_data = await _handle_create_booking(args, db)
    elif tool_name == "log_call_event":
        result_data = await _handle_log_call_event(args, db)
    else:
        result_data = {"error": f"Unknown tool: {tool_name}"}

    result_str = json.dumps(result_data)
    return {"results": [{"toolCallId": tool_call_id, "name": tool_name, "result": result_str}]}


@router.post("/tool/check_availability")
async def tool_check_availability(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    return await _handle_tool_request("check_availability", request, db)


@router.post("/tool/create_booking")
async def tool_create_booking(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    return await _handle_tool_request("create_booking", request, db)


@router.post("/tool/log_call_event")
async def tool_log_call_event(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    return await _handle_tool_request("log_call_event", request, db)
