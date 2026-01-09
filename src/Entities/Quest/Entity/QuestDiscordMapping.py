from sqlalchemy import Column, BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from src.Entities.BaseClass import Base


class QuestDiscordMapping(Base):
    __tablename__ = "quest_discord_mapping"

    id = Column(BigInteger, autoincrement=True, primary_key=True)
    current_value = Column(BigInteger, nullable=False, default=0)
    time_created = Column(DateTime, nullable=False)
    time_updated = Column(DateTime)

    quest_id = Column(BigInteger, ForeignKey("quest.id"))
    quest = relationship("Quest")

    discord_id = Column(BigInteger, ForeignKey("discord.id"))
    discord_user = relationship("DiscordUser")

    def __repr__(self):
        return f"QuestDiscordMapping(id={self.id}, DiscordUser={self.discord_user}, Quest={self.quest})"


# lazy loading to avoid circular imports
# noinspection PyUnresolvedReferences
from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser
# noinspection PyUnresolvedReferences
from src.Entities.Quest.Entity.Quest import Quest
