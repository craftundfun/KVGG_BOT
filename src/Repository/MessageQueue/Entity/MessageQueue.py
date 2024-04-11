from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from src.Repository.BaseClass import Base


class MessageQueue(Base):
    __tablename__ = 'message_queue'

    id = Column(Integer, primary_key=True, autoincrement=True)
    message = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    created_at = Column(DateTime, nullable=False)
    sent_at = Column(DateTime)
    error = Column(Boolean)
    time_to_sent = Column(DateTime)
    trigger_user_id = Column(Integer, ForeignKey('discord.id'))
    is_join_message = Column(Boolean)

    user = relationship('User')
    trigger_user = relationship('DiscordUser')

    def __repr__(self):
        return f"MessageQueue(id={self.id}, DiscordUser={self.trigger_user}, User={self.user})"
