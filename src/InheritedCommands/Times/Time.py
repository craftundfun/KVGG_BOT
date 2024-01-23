from __future__ import annotations

import string
from abc import ABC, abstractmethod


class Time(ABC):

    def __init__(self, name: string):
        self.name = name

    @abstractmethod
    def increaseTime(self, dcUserDb: dict, value: int, updateFormattedTime: bool = True):
        pass

    @abstractmethod
    def getTime(self, dcUserDb: dict) -> int | None:
        pass

    @abstractmethod
    def setFormattedTime(self, dcUserDb: dict, time: string):
        pass

    @abstractmethod
    def getFormattedTime(self, dcUserDb: dict) -> string:
        pass

    @abstractmethod
    def getStringForTime(self, dcUserDb: dict) -> string:
        pass

    def getName(self) -> string:
        return self.name
