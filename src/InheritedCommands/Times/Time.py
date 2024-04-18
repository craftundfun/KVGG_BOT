from __future__ import annotations

import string
from abc import ABC, abstractmethod

from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser


class Time(ABC):

    def __init__(self, name: string):
        self.name = name

    @abstractmethod
    def increaseTime(self, dcUserDb: DiscordUser, value: int):
        pass

    @abstractmethod
    def getTime(self, dcUserDb: DiscordUser) -> int:
        pass

    @abstractmethod
    def getStringForTime(self, dcUserDb: DiscordUser) -> string:
        pass

    def getName(self) -> string:
        return self.name
