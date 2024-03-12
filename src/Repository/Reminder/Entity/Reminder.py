from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.Repository.BaseClass import Base


class Reminder(Base):
    __tablename__ = "reminder"

    id: Mapped[int] = mapped_column(primary_key=True)
    content: Mapped[str]
    time_to_sent: Mapped[Optional[datetime]]
    sent_at: Mapped[Optional[datetime]]
    error: Mapped[Optional[bool]]
    repeat_in_minutes: Mapped[Optional[int]]
    whatsapp: Mapped[Optional[bool]]
    is_timer: Mapped[bool]

    discord_user_id: Mapped[int] = mapped_column(ForeignKey("discord.id"))
    discord_user: Mapped["DiscordUser"] = relationship("DiscordUser")

    def __repr__(self):
        return f"Reminder(id={self.id}, DiscordUser={self.discord_user})"
