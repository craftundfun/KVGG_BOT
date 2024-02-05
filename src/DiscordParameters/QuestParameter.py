from enum import Enum


class QuestDates(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

    @classmethod
    def getValues(cls) -> set[str]:
        return set(category.value for category in QuestDates)

    @classmethod
    def getQuestAmountForDate(cls, time: "QuestDates") -> int | None:
        """
        Returns the amount of quest allowed for each time.

        :param time: Which amounts to return
        :returns: int | None - None in case the date is cursed
        """
        match time:
            case QuestDates.DAILY:
                return QuestAmountsPerDate.DAILY.value
            case QuestDates.WEEKLY:
                return QuestAmountsPerDate.WEEKLY.value
            case QuestDates.MONTHLY:
                return QuestAmountsPerDate.MONTHLY.value
            case _:
                return None


class QuestAmountsPerDate(Enum):
    DAILY = 3
    WEEKLY = 3
    MONTHLY = 3
