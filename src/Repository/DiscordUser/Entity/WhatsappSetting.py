from typing import Optional, Any

from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.Repository.BaseClass import Base


# from src.Repository.DiscordUser.Entity.DiscordUser import DiscordUser


class WhatsappSetting(Base):
    __tablename__ = "whatsapp_setting"

    id: Mapped[int] = mapped_column(primary_key=True)
    receive_join_notification: Mapped[bool]
    receive_leave_notification: Mapped[bool]
    receive_uni_join_notification: Mapped[bool]
    receive_uni_leave_notification: Mapped[bool]
    suspend_times: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)

    discord_user_id: Mapped[int] = mapped_column(ForeignKey("discord.id"))
    discord_user: Mapped["DiscordUser"] = relationship("DiscordUser")

    def __repr__(self):
        return f"WhatsappSetting(id={self.id}, DiscordUser={self.discord_user})"
