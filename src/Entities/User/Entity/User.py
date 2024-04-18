from sqlalchemy import Column, BigInteger, String, DateTime, Float, Integer, JSON
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from src.Entities.BaseClass import Base


class User(Base):
    __tablename__ = 'user'

    id = Column(BigInteger, autoincrement=True, primary_key=True)
    firstname = Column(String(30))
    lastname = Column(String(30))
    nickname = Column(String(80))
    username = Column(String(80), nullable=False)
    email = Column(String(255))
    roles = Column(JSON)
    developer_mode = Column(Integer, default=0)
    salt = Column(String(80), nullable=False)
    password = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    deleted_at = Column(DateTime)
    phone_number = Column(String(255))
    api_key_whats_app = Column(String(30))
    discord_user_id = Column(BigInteger, ForeignKey('discord.id'))
    number_orders = Column(Float)
    number_pick_up = Column(Float)
    pick_up_index = Column(Float)
    always_vote_result_mail = Column(Integer, default=0, nullable=False)
    personal_number = Column(Integer)
    profile_picture = Column(String(255))
    developer_profile_picture = Column(String(255))
    api_key = Column(String(20))
    # noinspection PyTypeChecker
    discord_user = relationship("DiscordUser", foreign_keys=[discord_user_id])

    def __repr__(self):
        return f"User(id={self.id}, firstname={self.firstname}, lastname={self.lastname})"
