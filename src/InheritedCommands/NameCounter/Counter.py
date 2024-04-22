import string
from abc import ABC, abstractmethod


class Counter(ABC):

    def __init__(self, name: str, dcUserDb):
        self.name = name
        self.dcUserDb = dcUserDb

    def getNameOfCounter(self) -> string:
        return self.name

    def getDiscordUser(self):
        return self.dcUserDb

    @abstractmethod
    def getCounterValue(self) -> int:
        pass

    @abstractmethod
    async def setCounterValue(self, value: int):
        pass

    @abstractmethod
    def getCounterValueByDifferentDiscordUser(self, dcUserDb) -> int:
        pass

    def setDiscordUser(self, dcUserDb: dict):
        self.dcUserDb = dcUserDb
