from __future__ import annotations

from datetime import datetime

from src.InheritedCommands.NameCounter.Counter import Counter

FELIX_COUNTER_MINUTES = 20
FELIX_COUNTER_START_KEYWORD = 'start'
FELIX_COUNTER_STOP_KEYWORD = 'stop'
LIAR = 'https://tenor.com/view/anakin-liar-star-wars-lying-gif-8634649'


def getAllKeywords() -> list:
    return [FELIX_COUNTER_START_KEYWORD, FELIX_COUNTER_STOP_KEYWORD]


class FelixCounter(Counter):

    def __init__(self, dcUserDb=None):
        super().__init__('Felix', dcUserDb)

    def getCounterValue(self) -> int:
        if self.dcUserDb:
            return self.dcUserDb['felix_counter']
        return -1

    def setCounterValue(self, value: int):
        if self.dcUserDb:
            self.dcUserDb['felix_counter'] = value

    def getCounterValueByDifferentDiscordUser(self, dcUserDb) -> int:
        return dcUserDb['felix_counter']

    def setFelixTimer(self, date: datetime | None):
        if self.dcUserDb:
            self.dcUserDb['felix_counter_start'] = date

    def getFelixTimer(self) -> datetime | None:
        if self.dcUserDb:
            return self.dcUserDb['felix_counter_start']
        return None
