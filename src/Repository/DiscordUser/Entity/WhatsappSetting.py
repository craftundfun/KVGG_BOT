from sqlalchemy import Column, BigInteger, Integer
from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import relationship

from src.Repository.BaseClass import Base


# from src.Repository.DiscordUser.Entity.DiscordUser import DiscordUser

# TODO make repository out of this for users with phone number and api key
class WhatsappSetting(Base):
    __tablename__ = 'whatsapp_setting'

    id = Column(BigInteger, autoincrement=True, primary_key=True)
    discord_user_id = Column(BigInteger, ForeignKey('discord.id'), nullable=False)
    receive_join_notification = Column(Integer, default=1)
    receive_leave_notification = Column(Integer, default=1)
    receive_uni_join_notification = Column(Integer, default=1)
    receive_uni_leave_notification = Column(Integer, default=1)
    suspend_times = Column(JSON)
    # noinspection PyTypeChecker
    discord_user = relationship("DiscordUser", foreign_keys=discord_user_id)

    def __repr__(self):
        return f"WhatsappSetting(id={self.id}, DiscordUser={self.discord_user})"
