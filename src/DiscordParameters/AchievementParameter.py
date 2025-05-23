from enum import Enum


class AchievementParameter(Enum):
    ONLINE_TIME_HOURS = 50
    STREAM_TIME_HOURS = 50
    RELATION_ONLINE_TIME_HOURS = 25
    RELATION_STREAM_TIME_HOURS = 25
    RELATION_ACTIVITY_TIME_HOURS = 25
    XP_AMOUNT = 25000
    TIME_PLAYED_HOURS = 25

    COOKIE_AMOUNT = -1
    DAILY_QUEST_AMOUNT = -1
    WEEKLY_QUEST_AMOUNT = -1
    MONTHLY_QUEST_AMOUNT = -1
    BEST_MEME_OF_THE_MONTH_AMOUNT = -1
    WORST_MEME_OF_THE_MONTH_AMOUNT = -1
    TIME_PLAYED_AMOUNT = -1

    ONLINE = "online"
    STREAM = "stream"
    XP = "xp"
    RELATION_ONLINE = "relation_online"
    RELATION_STREAM = "relation_stream"
    RELATION_ACTIVITY = "relation_activity"
    COOKIE = "cookie"
    ANNIVERSARY = "anniversary"
    DAILY_QUEST = "daily_quest"
    WEEKLY_QUEST = "weekly_quest"
    MONTHLY_QUEST = "monthly_quest"
    BEST_MEME_OF_THE_MONTH = "best_meme"
    WORST_MEME_OF_THE_MONTH = "worst_meme"
    TIME_PLAYED = "time_played"
