from pydantic import BaseModel
from typing import Any, Optional


class VapiFunctionCall(BaseModel):
    name: str
    arguments: dict[str, Any]


class VapiToolCall(BaseModel):
    id: str
    type: str = "function"
    function: VapiFunctionCall


class VapiMessage(BaseModel):
    type: str
    toolCallList: Optional[list[VapiToolCall]] = None
    toolCalls: Optional[list[VapiToolCall]] = None

    def get_tool_calls(self) -> list[VapiToolCall]:
        return self.toolCallList or self.toolCalls or []


class VapiWebhookPayload(BaseModel):
    message: VapiMessage


class CheckAvailabilityArgs(BaseModel):
    date: str  # YYYY-MM-DD, e.g. "2026-03-03"
    # host_id intentionally omitted — host is auto-selected by the backend


class CreateBookingArgs(BaseModel):
    caller_name: str
    caller_email: str
    host_id: str          # UUID from the check_availability slot response
    start_time: str
    end_time: str
    title: Optional[str] = "Meeting"   # meeting purpose as stated by the caller
    notes: Optional[str] = None


class LogCallEventArgs(BaseModel):
    event_type: str
    host_id: Optional[str] = None
    booking_id: Optional[str] = None
    payload: Optional[str] = None  # VAPI sends payload as a string
    details: Optional[dict[str, Any]] = None


class VapiToolResult(BaseModel):
    toolCallId: str
    result: Any


class VapiResponse(BaseModel):
    results: list[VapiToolResult]
