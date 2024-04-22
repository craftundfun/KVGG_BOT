from sqlalchemy import Column, BigInteger, String
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from src.Entities.BaseClass import Base


class User(Base):
    __tablename__ = 'user'

    id = Column(BigInteger, autoincrement=True, primary_key=True)
    firstname = Column(String(30))
    lastname = Column(String(30))
    phone_number = Column(String(255))
    api_key_whats_app = Column(String(30))
    discord_user_id = Column(BigInteger, ForeignKey('discord.id'))
    api_key = Column(String(20))
    # noinspection PyTypeChecker
    discord_user = relationship("DiscordUser", foreign_keys=[discord_user_id])

    def __repr__(self):
        return f"User(id={self.id}, firstname={self.firstname}, lastname={self.lastname})"
