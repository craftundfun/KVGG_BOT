from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.Repository.BaseClass import Base


class Meme(Base):
    __tablename__ = "meme"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int]
    likes: Mapped[int]
    created_at: Mapped[datetime]

    discord_id: Mapped[int] = mapped_column(ForeignKey("discord.id"))
    discord_user: Mapped["DiscordUser"] = relationship("DiscordUser")

    def __repr__(self):
        return f"Meme(id={self.id}, DiscordUser={self.discord_user})"
