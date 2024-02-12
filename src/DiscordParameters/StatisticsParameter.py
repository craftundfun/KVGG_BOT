from enum import Enum


class StatisticsParameter(Enum):
    # time types
    WEEKLY = "WEEK"
    MONTHLY = "MONTH"
    YEARLY = "YEAR"

    # data types
    ONLINE = "online"
    STREAM = "stream"
    MESSAGE = "message"
    COMMAND = "command"
    ACTIVITY = "activity"
