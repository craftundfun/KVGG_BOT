from datetime import datetime

from sqlalchemy import Column, ForeignKey, Integer, DateTime, BigInteger, JSON
from sqlalchemy.orm import relationship

from src.Entities.BaseClass import Base


class EventHistory(Base):
    __tablename__ = "event_history"

    id = Column(BigInteger, primary_key=True, index=True)
    discord_id = Column(BigInteger, ForeignKey("discord.id"), nullable=False)
    event_id = Column(BigInteger, ForeignKey("event.id"), nullable=False)
    time = Column(DateTime, nullable=False, default=datetime.now)
    additional_data = Column(JSON, nullable=True, default=None)

    event = relationship("Event")
    discord_user = relationship("DiscordUser", back_populates="event_history", uselist=True)

    def __init__(self, discord_id: int, event_id: int, additional_data: dict | None = None):
        super().__init__()

        self.discord_id = discord_id
        self.event_id = event_id
        self.additional_data = additional_data


# lazy loading the relationship
# noinspection PyUnresolvedReferences
from src.Entities.History.Entity.Event import Event
# noinspection PyUnresolvedReferences
from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser
