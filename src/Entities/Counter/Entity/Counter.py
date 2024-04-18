from sqlalchemy import Column, Integer, Text, VARCHAR

from src.Entities.BaseClass import Base


class Counter(Base):
    __tablename__ = 'counter'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(VARCHAR(100), nullable=False)
    description = Column(VARCHAR(100), nullable=False)
    tts_voice_line = Column(Text)

    def __repr__(self):
        return f"Counter(id={self.id}, name={self.name})"
