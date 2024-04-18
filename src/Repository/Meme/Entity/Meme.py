from sqlalchemy import Column, BigInteger, DateTime, Boolean, Text
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from src.Repository.BaseClass import Base


class Meme(Base):
    __tablename__ = 'meme'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    message_id = Column(BigInteger, nullable=False)
    discord_id = Column(BigInteger, ForeignKey('discord.id'), nullable=False)
    likes = Column(BigInteger, default=0, nullable=False)
    created_at = Column(DateTime, nullable=False)
    media_link = Column(Text)
    winner = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime)
    # noinspection PyTypeChecker
    discord_user = relationship("DiscordUser", foreign_keys=discord_id)

    def __repr__(self):
        return f"Meme(id={self.id}, DiscordUser={self.discord_user})"
