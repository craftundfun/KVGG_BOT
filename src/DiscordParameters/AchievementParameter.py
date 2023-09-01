from enum import Enum


class AchievementParameter(Enum):
    ONLINE_TIME_HOURS = 50
    STREAM_TIME_HOURS = 50
    XP_AMOUNT = 10000

    ONLINE = "online"
    STREAM = "stream"
    XP = "xp"
