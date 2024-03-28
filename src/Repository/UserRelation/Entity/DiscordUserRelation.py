from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.Repository.BaseClass import Base


# from src.Repository.DiscordUser.Entity.DiscordUser import DiscordUser


class DiscordUserRelation(Base):
    __tablename__ = "discord_user_relation"

    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[int]
    created_at: Mapped[datetime]
    type: Mapped[str]

    discord_user_id_1: Mapped[int] = mapped_column(ForeignKey("discord.id"))
    discord_user_1: Mapped["DiscordUser"] = relationship(
        "DiscordUser",
        foreign_keys=[discord_user_id_1]
    )

    discord_user_id_2: Mapped[int] = mapped_column(ForeignKey("discord.id"))
    discord_user_2: Mapped["DiscordUser"] = relationship(
        "DiscordUser",
        foreign_keys=[discord_user_id_2]
    )

    def __repr__(self):
        return (f"DiscordUserRelation(id={self.id}, DiscordUser1={self.discord_user_1},"
                f" DiscordUser2={self.discord_user_2})")
