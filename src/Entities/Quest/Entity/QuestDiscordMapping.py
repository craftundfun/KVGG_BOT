from sqlalchemy import Column, BigInteger, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from src.Entities.BaseClass import Base


class QuestDiscordMapping(Base):
    __tablename__ = "quest_discord_mapping"

    id = Column(BigInteger, autoincrement=True, primary_key=True)
    current_value = Column(BigInteger, nullable=False, default=0)
    time_created = Column(DateTime, nullable=False)
    time_updated = Column(DateTime)
    additional_info = Column(JSON, nullable=True, default=True)

    quest_id = Column(BigInteger, ForeignKey("quest.id"))
    quest = relationship("Quest")

    discord_id = Column(BigInteger, ForeignKey("discord.id"))
    discord_user = relationship("DiscordUser")

    def __repr__(self):
        return f"QuestDiscordMapping(id={self.id}, DiscordUser={self.discord_user}, Quest={self.quest})"
