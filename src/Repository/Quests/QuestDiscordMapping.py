from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.Repository.BaseClass import Base


class QuestDiscordMapping(Base):
    __tablename__ = "quest_discord_mapping"

    id: Mapped[int] = mapped_column(primary_key=True)
    current_value: Mapped[int]
    time_created: Mapped[datetime]
    time_updated: Mapped[datetime]

    quest_id: Mapped[int] = mapped_column(ForeignKey("quest.id"))
    quest: Mapped["Quest"] = relationship("Quest")

    discord_id: Mapped[int] = mapped_column(ForeignKey("discord.id"))
    discord_user: Mapped["DiscordUser"] = relationship("DiscordUser")

    def __repr__(self):
        return f"QuestDiscordMapping(id={self.id}, DiscordUser={self.discord_user}, Quest={self.quest})"
