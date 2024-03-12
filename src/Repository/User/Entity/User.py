from typing import Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.Repository.BaseClass import Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    firstname: Mapped[Optional[str]]
    lastname: Mapped[Optional[str]]
    nickname: Mapped[Optional[str]]
    api_key: Mapped[Optional[str]]

    discord_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("discord.id"))
    discord_user: Mapped[Optional["DiscordUser"]] = relationship("DiscordUser")

    def __repr__(self):
        return f"User(id={self.id}, firstname={self.firstname}, lastname={self.lastname})"
