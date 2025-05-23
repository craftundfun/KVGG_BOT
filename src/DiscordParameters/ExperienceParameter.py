from enum import Enum


class ExperienceParameter(Enum):
    XP_FOR_MESSAGE = 2
    XP_FOR_ONLINE = 10
    XP_FOR_STREAMING = 5
    XP_FOR_COMMAND = 1

    XP_BOOST_MULTIPLIER_ONLINE = 2
    XP_BOOST_MULTIPLIER_SPIN = 2
    XP_BOOST_MULTIPLIER_BIRTHDAY = 3
    XP_BOOST_MULTIPLIER_STREAM = 3
    XP_BOOST_MULTIPLIER_RELATION_ONLINE = 2
    XP_BOOST_MULTIPLIER_RELATION_STREAM = 2
    XP_BOOST_MULTIPLIER_COOKIE = 2
    XP_BOOST_MULTIPLIER_DAILY_QUEST = 2
    XP_BOOST_MULTIPLIER_WEEKLY_QUEST = 3
    XP_BOOST_MULTIPLIER_MONTHLY_QUEST = 4
    XP_BOOST_MULTIPLIER_BEST_MEME = 10
    XP_BOOST_MULTIPLIER_WORST_MEME = 0.5
    XP_BOOST_MULTIPLIER_TIME_PLAYED = 4
    XP_BOOST_MULTIPLIER_RELATION_ACTIVITY = 2

    XP_BOOST_ONLINE_DURATION = 180
    XP_BOOST_BIRTHDAY_DURATION = 1440
    XP_BOOST_SPIN_DURATION = 60
    XP_BOOST_STREAM_DURATION = 300
    XP_BOOST_RELATION_ONLINE_DURATION = 30
    XP_BOOST_RELATION_STREAM_DURATION = 30
    XP_BOOST_COOKIE_DURATION = 10
    XP_BOOST_DAILY_QUEST_DURATION = 10
    XP_BOOST_WEEKLY_QUEST_DURATION = 60
    XP_BOOST_MONTHLY_QUEST_DURATION = 420
    XP_BOOST_BEST_MEME_DURATION = 120
    XP_BOOST_WORST_MEME_DURATION = 120
    XP_BOOST_TIME_PLAYED_DURATION = 120
    XP_BOOST_RELATION_ACTIVITY_DURATION = 30

    DESCRIPTION_ONLINE = 'Online'
    DESCRIPTION_BIRTHDAY = 'Geburtstag'
    DESCRIPTION_SPIN = 'Spin'
    DESCRIPTION_STREAM = 'Stream'
    DESCRIPTION_RELATION_ONLINE = 'Online-Paerchen'
    DESCRIPTION_RELATION_STREAM = 'Stream-Paerchen'
    DESCRIPTION_COOKIE = "Keks"
    DESCRIPTION_DAILY_QUEST = "Daily-Quest"
    DESCRIPTION_WEEKLY_QUEST = "Weekly-Quest"
    DESCRIPTION_MONTHLY_QUEST = "Monthly-Quest"
    DESCRIPTION_BEST_MEME = "bestes Meme des Monats"
    DESCRIPTION_WORST_MEME = "schlechtestes Meme des Monats"
    DESCRIPTION_TIME_PLAYED = "Game"
    DESCRIPTION_RELATION_ACTIVITY = "Spiele-Paerchen"

    WAIT_X_DAYS_BEFORE_NEW_SPIN = 7
    SPIN_WIN_PERCENTAGE = 25
    WAIT_X_DAYS_BEFORE_NEW_COOKIE_BOOST = 1

    MAX_XP_BOOSTS_INVENTORY = 30

    XP_WEEKEND_VALUE = 2
