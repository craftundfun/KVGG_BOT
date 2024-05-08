from sqlalchemy import Column, String, Integer

from src.Entities.BaseClass import Base


class AllCurrentServerStats(Base):
    __tablename__ = 'all_current_server_stats'

    statistic_type = Column(String(80), nullable=False, primary_key=True)
    statistic_time = Column(String(80), nullable=False, primary_key=True)
    value = Column(Integer, nullable=False, default=0)
    user_count = Column(Integer, nullable=False, default=0)

    def __repr__(self):
        return (f"AllCurrentDiscordStats(statistic_type={self.statistic_type}, statistic_time={self.statistic_time}, "
                f"value={self.value})")
