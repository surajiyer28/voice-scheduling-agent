import uuid
from datetime import time
from sqlalchemy import SmallInteger, Boolean, Time, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Availability(Base):
    __tablename__ = "availability"

    __table_args__ = (UniqueConstraint("host_id", "day_of_week", name="uq_host_day"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    host_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hosts.id", ondelete="CASCADE"),
        nullable=False,
    )
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, default=time(9, 0), nullable=False)
    end_time: Mapped[time] = mapped_column(Time, default=time(17, 0), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    host: Mapped["Host"] = relationship("Host", back_populates="availability")
