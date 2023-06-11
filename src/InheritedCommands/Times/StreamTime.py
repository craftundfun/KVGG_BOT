from __future__ import annotations

import string

from src.Helper.getFormattedTime import getFormattedTime
from src.InheritedCommands.Times.Time import Time


class StreamTime(Time):

    def __init__(self):
        super().__init__('Stream')

    def increaseTime(self, dcUserDb, value: int, updateFormattedTime: bool = True):
        dcUserDb['time_streamed'] = dcUserDb['time_streamed'] + value

        if updateFormattedTime:
            dcUserDb['formatted_stream_time'] = getFormattedTime(dcUserDb['time_streamed'])

    def getTime(self, dcUserDb) -> int | None:
        return dcUserDb['time_streamed']

    def getFormattedTime(self, dcUserDb) -> string:
        return dcUserDb['formatted_stream_time']

    def getStringForTime(self, dcUserDb) -> string:
        return "<@%s> hat bereits %s Stunden gestreamt!" % (dcUserDb['user_id'], dcUserDb['formatted_stream_time'])

    def setFormattedTime(self, dcUserDb, time: string):
        dcUserDb['formatted_stream_time'] = string
