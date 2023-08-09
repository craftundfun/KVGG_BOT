from __future__ import annotations

import string

from src.Helper import GetFormattedTime
from src.InheritedCommands.Times.Time import Time


class UniversityTime(Time):

    def __init__(self):
        super().__init__('Uni')

    def increaseTime(self, dcUserDb, value: int, updateFormattedTime: bool = True):
        dcUserDb['university_time_online'] = dcUserDb['university_time_online'] + value

        if updateFormattedTime:
            dcUserDb['formated_university_time'] = getFormattedTime.getFormattedTime(dcUserDb['university_time_online'])

    def getTime(self, dcUserDb) -> int | None:
        return dcUserDb['university_time_online']

    def getFormattedTime(self, dcUserDb) -> string:
        return dcUserDb['formated_university_time']

    def getStringForTime(self, dcUserDb) -> string:
        if dcUserDb['formated_university_time'] is None:
            return "Es liegt keine formatierte Zeit vor!"
        return "<@%s> hat bereits %s Stunden studiert!" % (dcUserDb['user_id'], dcUserDb['formated_university_time'])

    def setFormattedTime(self, dcUserDb, time: string):
        dcUserDb['formated_university_time'] = time
