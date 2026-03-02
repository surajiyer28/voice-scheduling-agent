import uuid
from datetime import time
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional


class AvailabilitySlot(BaseModel):
    day_of_week: int
    start_time: time
    end_time: time
    is_available: bool = True

    @field_validator("day_of_week")
    @classmethod
    def validate_day(cls, v: int) -> int:
        if not 0 <= v <= 6:
            raise ValueError("day_of_week must be between 0 and 6")
        return v

    @model_validator(mode="after")
    def validate_times(self) -> "AvailabilitySlot":
        if self.is_available and self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class AvailabilityUpdate(BaseModel):
    slots: list[AvailabilitySlot]

    @field_validator("slots")
    @classmethod
    def validate_all_days(cls, v: list[AvailabilitySlot]) -> list[AvailabilitySlot]:
        if len(v) != 7:
            raise ValueError("Must provide exactly 7 slots (one per day)")
        days = {slot.day_of_week for slot in v}
        if days != set(range(7)):
            raise ValueError("Must include all days 0-6")
        return v


class AvailabilityResponse(BaseModel):
    id: uuid.UUID
    host_id: uuid.UUID
    day_of_week: int
    start_time: time
    end_time: time
    is_available: bool

    model_config = {"from_attributes": True}
