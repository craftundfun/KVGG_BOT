from enum import Enum


class StatisticsParameter(Enum):
    # time types
    DAILY = "DAY"
    WEEKLY = "WEEK"
    MONTHLY = "MONTH"
    YEARLY = "YEAR"

    # data types
    ONLINE = "online"
    STREAM = "stream"
    MESSAGE = "message"
    COMMAND = "command"
    ACTIVITY = "activity"
    UNIVERSITY = "university"

    @classmethod
    def getTypeValues(cls) -> list[str]:
        return [cls.ONLINE.value,
                cls.STREAM.value,
                cls.MESSAGE.value,
                cls.COMMAND.value,
                cls.ACTIVITY.value,
                cls.UNIVERSITY.value, ]
