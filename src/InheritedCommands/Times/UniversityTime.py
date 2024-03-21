from __future__ import annotations

import string

from src.Helper.GetFormattedTime import getFormattedTime
from src.InheritedCommands.Times.Time import Time
from src.Repository.DiscordUser.Entity.DiscordUser import DiscordUser


class UniversityTime(Time):

    def __init__(self):
        super().__init__('Uni')

    def increaseTime(self, dcUserDb: DiscordUser, value: int):
        dcUserDb.university_time_online += value

    def getTime(self, dcUserDb: DiscordUser) -> int | None:
        return dcUserDb.university_time_online

    def getStringForTime(self, dcUserDb: DiscordUser) -> string:
        return (f"<@{dcUserDb.user_id}> hat bereits {getFormattedTime(dcUserDb.university_time_online)} "
                f"Stunden studiert!")
