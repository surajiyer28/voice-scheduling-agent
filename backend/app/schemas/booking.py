import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class BookingResponse(BaseModel):
    id: uuid.UUID
    host_id: Optional[uuid.UUID]
    caller_name: str
    caller_email: str
    title: str
    notes: Optional[str]
    start_time: datetime
    end_time: datetime
    calendar_event_id: Optional[str]
    status: str
    meeting_link: Optional[str]
    email_sent: bool
    delete_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


