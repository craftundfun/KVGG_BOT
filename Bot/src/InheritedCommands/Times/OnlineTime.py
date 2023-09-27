from __future__ import annotations

import string

from Bot.src.Helper.GetFormattedTime import getFormattedTime
from Bot.src.InheritedCommands.Times.Time import Time


class OnlineTime(Time):

    def __init__(self):
        super().__init__("Online")

    def increaseTime(self, dcUserDb, value: int, updateFormattedTime: bool = True):
        dcUserDb['time_online'] = dcUserDb['time_online'] + value

        if updateFormattedTime:
            dcUserDb['formated_time'] = getFormattedTime(dcUserDb['time_online'])

    def getTime(self, dcUserDb) -> int | None:
        return dcUserDb['time_online']

    def getFormattedTime(self, dcUserDb) -> string:
        return dcUserDb['formated_time']

    def getStringForTime(self, dcUserDb) -> string:
        if dcUserDb['formated_time'] is None:
            return "Es liegt keine formatierte Zeit vor!"
        return "<@%s> war bereits %s Stunden online!" % (dcUserDb['user_id'], dcUserDb['formated_time'])

    def setFormattedTime(self, dcUserDb, time: string):
        dcUserDb['formated_time'] = time
