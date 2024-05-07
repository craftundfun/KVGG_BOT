from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship

from src.Entities.BaseClass import Base


class DiscordRoleMapping(Base):
    __tablename__ = 'discord_role_mapping'

    id = Column(Integer, primary_key=True, autoincrement=True)
    discord_id = Column(Integer, ForeignKey('discord.id'), nullable=False)
    role_id = Column(Integer, ForeignKey('discord_role.id'), nullable=False)
    # noinspection PyTypeChecker
    discord_user = relationship("DiscordUser", foreign_keys=discord_id)
    # noinspection PyTypeChecker
    discord_role = relationship("DiscordRole", foreign_keys=role_id)

    def __repr__(self):
        return f"DiscordRoleMapping(id={self.id}, DiscordUser={self.discord_user}, DiscordRole={self.discord_role})"
