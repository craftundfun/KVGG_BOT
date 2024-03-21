from __future__ import annotations

import string

from src.Helper.GetFormattedTime import getFormattedTime
from src.InheritedCommands.Times.Time import Time
from src.Repository.DiscordUser.Entity.DiscordUser import DiscordUser


class OnlineTime(Time):

    def __init__(self):
        super().__init__("Online")

    # TODO test
    def increaseTime(self, dcUserDb: DiscordUser, value: int):
        dcUserDb.time_online += value

    # TODO test
    def getTime(self, dcUserDb: DiscordUser) -> int:
        return dcUserDb.time_online

    # TODO test
    def getStringForTime(self, dcUserDb: DiscordUser) -> string:
        return f"<@{dcUserDb.user_id}> war bereits {getFormattedTime(dcUserDb.time_online)} Stunden online!"
