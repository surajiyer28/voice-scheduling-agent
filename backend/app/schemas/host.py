import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr
from typing import Optional


class HostBase(BaseModel):
    email: str
    name: str
    picture: Optional[str] = None


class HostCreate(HostBase):
    google_id: str
    google_access_token: Optional[str] = None
    google_refresh_token: Optional[str] = None
    google_token_expiry: Optional[datetime] = None


class HostUpdate(BaseModel):
    name: Optional[str] = None
    picture: Optional[str] = None
    timezone: Optional[str] = None


class HostRegister(BaseModel):
    google_id: str
    email: str
    name: str
    picture: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expiry: Optional[datetime] = None


class HostResponse(HostBase):
    id: uuid.UUID
    google_id: str
    calendar_id: str
    timezone: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
