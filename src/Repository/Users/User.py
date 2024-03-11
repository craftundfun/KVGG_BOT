from datetime import datetime
from typing import Optional, Any

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.Repository.BaseClass import Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    firstname: Mapped[Optional[str]]
    lastname: Mapped[Optional[str]]
    nickname: Mapped[Optional[str]]
    username: Mapped[str]
    email: Mapped[Optional[str]]
    roles: Mapped[dict[str, Any]] = mapped_column(JSON)
    developer_mode: Mapped[Optional[bool]]
    salt: Mapped[str]
    password: Mapped[str]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    deleted_at: Mapped[Optional[datetime]]
    phone_number: Mapped[Optional[str]]
    api_key_whats_app: Mapped[Optional[str]]
    number_orders: Mapped[Optional[float]]
    number_pick_up: Mapped[Optional[float]]
    pick_up_index: Mapped[Optional[float]]
    always_vote_result_mail: Mapped[bool]
    personal_number: Mapped[int]
    profile_picture: Mapped[Optional[str]]
    developer_profile_picture: Mapped[Optional[str]]
    api_key: Mapped[Optional[str]]

    discord_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("discord.id"))
    discord_user: Mapped[Optional["DiscordUser"]] = relationship("DiscordUser")

    def __repr__(self):
        return f"User(id={self.id}, firstname={self.firstname}, lastname={self.lastname})"
