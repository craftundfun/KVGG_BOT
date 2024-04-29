from sqlalchemy import Column, BigInteger, String, DateTime, null
from sqlalchemy.orm import relationship

from src.Entities.BaseClass import Base


class DiscordUser(Base):
    __tablename__ = 'discord'

    id = Column(BigInteger, autoincrement=True, primary_key=True)
    guild_id = Column(String(30), default=null())
    channel_id = Column(String(30))
    user_id = Column(String(30), nullable=False)
    username = Column(String(255), nullable=False)
    joined_at = Column(DateTime)
    last_online = Column(DateTime)
    time_online = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False)
    message_count_all_time = Column(BigInteger, nullable=False, default=0)
    muted_at = Column(DateTime)
    full_muted_at = Column(DateTime)
    time_streamed = Column(BigInteger, nullable=False, default=0)
    profile_picture_discord = Column(String(300))
    university_time_online = Column(BigInteger)
    felix_counter_start = Column(DateTime)
    command_count_all_time = Column(BigInteger, nullable=False, default=0)
    discord_name = Column(String(255))

    user = relationship("User", back_populates="discord_user")
    # use useList, otherwise that would be a list
    whatsapp_setting = relationship("WhatsappSetting", back_populates="discord_user", uselist=False)
    experience = relationship("Experience", back_populates="discord_user")
    counter_mappings = relationship("CounterDiscordMapping", back_populates="discord_user")
    current_discord_statistics = relationship("CurrentDiscordStatistic", back_populates="discord_user")
    memes = relationship("Meme", back_populates="discord_user")
    game_mappings = relationship("GameDiscordMapping", back_populates="discord_user")
    quest_mappings = relationship("QuestDiscordMapping", back_populates="discord_user")

    def __repr__(self):
        return f"DiscordUser(id={self.id}, username={self.username})"
