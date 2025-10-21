from sqlalchemy import Column, BigInteger, Enum

from src.DiscordParameters.HistoryEvent import HistoryEvent
from src.Entities.BaseClass import Base


class Event(Base):
    __tablename__ = 'event'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    value = Column(Enum(HistoryEvent), nullable=False, unique=True)

    def __repr__(self):
        return f"Event(id={self.id}, value={self.value})"
