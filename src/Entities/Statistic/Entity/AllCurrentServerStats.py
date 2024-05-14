from sqlalchemy import Column, String, Integer

from src.Entities.BaseClass import Base


class AllCurrentServerStats(Base):
    __tablename__ = 'all_current_server_stats'
    __table_args__ = {'info': {'is_view': True, 'read_only': True}}

    statistic_type = Column(String(80), primary_key=True)
    statistic_time = Column(String(80), primary_key=True)
    value = Column(Integer)
    user_count = Column(Integer)

    def __repr__(self):
        return (f"AllCurrentDiscordStats(statistic_type={self.statistic_type}, statistic_time={self.statistic_time}, "
                f"value={self.value})")
