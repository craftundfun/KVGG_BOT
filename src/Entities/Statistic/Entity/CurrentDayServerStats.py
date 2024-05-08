from sqlalchemy import Column, Integer, String

from src.Entities.BaseClass import Base


class CurrentDayServerStats(Base):
    __tablename__ = 'current_day_server_stats'

    value = Column(Integer)
    # not a real primary key, but we will only have one entry for each statistic type and SQLAlchemy requires
    # a primary key
    statistic_type = Column(String, primary_key=True)

    def __repr__(self):
        return f"CurrentDayServerStats(value={self.value}, statistic_type={self.statistic_type})"
