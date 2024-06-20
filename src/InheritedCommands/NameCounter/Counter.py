import string
from abc import ABC, abstractmethod

from discord import Client

from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser


class Counter(ABC):

    def __init__(self, name: str, dcUserDb: DiscordUser, client: Client):
        self.name = name
        self.dcUserDb = dcUserDb
        self.client = client

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
