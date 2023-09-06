from enum import Enum


class AchievementParameter(Enum):
    ONLINE_TIME_HOURS = 50
    STREAM_TIME_HOURS = 50
    RELATION_ONLINE_TIME_HOURS = 25
    RELATION_STREAM_TIME_HOURS = 25
    XP_AMOUNT = 25000

    ONLINE = "online"
    STREAM = "stream"
    XP = "xp"
    RELATION_ONLINE = "relation_online"
    RELATON_STREAM = "relation_stream"
