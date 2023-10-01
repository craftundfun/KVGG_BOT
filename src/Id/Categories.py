from enum import Enum


class TrackedCategories(Enum):
    SERVERVERWALTUNG = 623227011422355526  # TODO comment out

    GAMING = 623226859093491743

    LABERECKE = 693584839521206396

    BESONDERE_EVENTS = 915226265903050762

    @classmethod
    def getValues(cls) -> set[int]:
        return set(channel.value for channel in TrackedCategories)


class UniversityCategory(Enum):
    UNIVERSITY = 803323466157129818

    @classmethod
    def getValues(cls) -> set[int]:
        return set(channel.value for channel in UniversityCategory)
