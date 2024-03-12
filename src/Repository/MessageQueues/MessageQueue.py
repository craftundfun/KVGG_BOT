from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.Repository.BaseClass import Base
from src.Repository.DiscordUsers.DiscordUser import DiscordUser
from src.Repository.Users.User import User


class MessageQueue(Base):
    __tablename__ = "message_queue"

    id: Mapped[int] = mapped_column(primary_key=True)
    message: Mapped[str]
    created_at: Mapped[datetime]
    sent_at: Mapped[Optional[datetime]]
    error: Mapped[Optional[bool]]
    time_to_sent: Mapped[Optional[datetime]]
    is_join_message: Mapped[Optional[bool]]

    trigger_user_id: Mapped[int] = mapped_column(ForeignKey("discord.id"))
    discord_user: Mapped["DiscordUser"] = relationship("DiscordUser")

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    user: Mapped["User"] = relationship("User")

    def __repr__(self):
        return f"MessageQueue(id={self.id}, DiscordUser={self.discord_user}, User={self.user})"
