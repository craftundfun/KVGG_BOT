from sqlalchemy import Column, Enum, String, Text, BigInteger

from src.Entities.BaseClass import Base


class Quest(Base):
    __tablename__ = 'quest'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    time_type = Column(Enum('daily', 'weekly', 'monthly'), nullable=False)
    type = Column(String(80), nullable=False)
    description = Column(Text, nullable=False)
    value_to_reach = Column(BigInteger, nullable=False)
    unit = Column(String(255), nullable=False, default='Minuten')

    def __repr__(self):
        return f"Quest(id={self.id})"
