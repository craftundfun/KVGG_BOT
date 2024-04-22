from __future__ import annotations

import string

from src.Helper.GetFormattedTime import getFormattedTime
from src.InheritedCommands.Times.Time import Time
from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser


class StreamTime(Time):

    def __init__(self):
        super().__init__('Stream')

    def increaseTime(self, dcUserDb: DiscordUser, value: int):
        dcUserDb.time_streamed += value

    def getTime(self, dcUserDb: DiscordUser) -> int | None:
        return dcUserDb.time_streamed

    def getStringForTime(self, dcUserDb: DiscordUser) -> string:
        return f"<@{dcUserDb.user_id}> hat bereits {getFormattedTime(dcUserDb.time_streamed)} Stunden gestreamt!"
