from sqlalchemy import Column, Integer, Text

from src.Entities.BaseClass import Base


class Quote(Base):
    __tablename__ = 'quotes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    quote = Column(Text, nullable=False)
    message_external_id = Column(Integer, nullable=False)

    def __repr__(self):
        return f"Quote(id={self.id})"
