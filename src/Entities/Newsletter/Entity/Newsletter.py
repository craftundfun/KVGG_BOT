from sqlalchemy import Column, BigInteger, Text, DateTime

from src.Entities.BaseClass import Base


class Newsletter(Base):
    __tablename__ = 'newsletter'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"Newsletter(id={self.id})"
