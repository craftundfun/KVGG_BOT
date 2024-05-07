from sqlalchemy import Column, String, Integer

from src.Entities.BaseClass import Base


class DiscordRole(Base):
    __tablename__ = 'discord_role'

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)

    def __repr__(self):
        return f"DiscordRole(id={self.id}, Name={self.name})"
