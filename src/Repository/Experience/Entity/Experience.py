from datetime import datetime
from typing import Optional, Any

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.Repository.BaseClass import Base


class Experience(Base):
    __tablename__ = "experience"

    id: Mapped[int] = mapped_column(primary_key=True)
    xp_amount: Mapped[Optional[int]]
    xp_boosts_inventory: Mapped[dict[str, Any]] = mapped_column(JSON)
    last_spin_for_boost: Mapped[Optional[datetime]]
    active_xp_boosts: Mapped[dict[str, Any]] = mapped_column(JSON)
    last_cookie_boost: Mapped[Optional[datetime]]
    time_to_send_spin_reminder: Mapped[Optional[datetime]]

    discord_user_id: Mapped[int] = mapped_column(ForeignKey("discord.id"))
    discord_user: Mapped["DiscordUser"] = relationship("DiscordUser")

    def __repr__(self):
        return f"Experience(id={self.id}, DiscordUser={self.discord_user})"
