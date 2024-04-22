from sqlalchemy import Column, ForeignKey, Integer, Text, DateTime, Boolean
from sqlalchemy.orm import relationship

from src.Entities.BaseClass import Base


class Reminder(Base):
    __tablename__ = 'reminder'

    id = Column(Integer, primary_key=True, autoincrement=True)
    discord_user_id = Column(Integer, ForeignKey('discord.id'), nullable=False)
    content = Column(Text, nullable=False)
    time_to_sent = Column(DateTime)
    sent_at = Column(DateTime)
    error = Column(Integer, default=0)
    repeat_in_minutes = Column(Integer)
    whatsapp = Column(Boolean, default=False)
    is_timer = Column(Boolean, nullable=False)
    # noinspection PyTypeChecker
    discord_user = relationship("DiscordUser", foreign_keys=discord_user_id)

    def __repr__(self):
        return f"Reminder(id={self.id}, DiscordUser={self.discord_user})"
