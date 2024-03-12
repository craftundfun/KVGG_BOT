from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.Repository.BaseClass import Base
from src.Repository.Experiences.Experience import Experience
from src.Repository.Users.User import User


class DiscordUser(Base):
    __tablename__ = 'discord'

    id: Mapped[int] = mapped_column(primary_key=True)
    guild_id: Mapped[str]
    channel_id: Mapped[Optional[str]]
    user_id: Mapped[str]
    username: Mapped[str]
    joined_at: Mapped[Optional[datetime]]
    last_online: Mapped[Optional[datetime]]
    time_online: Mapped[Optional[int]]
    created_at: Mapped[datetime]
    formated_time: Mapped[Optional[str]]
    message_count_all_time: Mapped[Optional[int]]
    muted_at: Mapped[Optional[datetime]]
    full_muted_at: Mapped[Optional[datetime]]
    time_streamed: Mapped[datetime]
    started_stream_at: Mapped[Optional[datetime]]
    formatted_stream_time: Mapped[Optional[str]]
    started_webcam_at: Mapped[Optional[datetime]]
    university_time_online: Mapped[Optional[int]]
    formated_university_time: Mapped[Optional[str]]
    profile_picture_discord: Mapped[Optional[str]]
    felix_counter_start: Mapped[Optional[datetime]]
    command_count_all_time: Mapped[int]
    felix_counter: Mapped[Optional[int]]

    user: Mapped["User"] = relationship("User", back_populates="discord_user")
    experience: Mapped["Experience"] = relationship("Experience", back_populates="discord_user")

    def __repr__(self):
        return f"DiscordUser(id={self.id}, username={self.username})"
