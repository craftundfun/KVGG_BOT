from __future__ import annotations

import logging
from datetime import datetime

from discord import Member
from sqlalchemy import null
from sqlalchemy.orm import Session

from src.Helper.SendDM import sendDM, separator
from src.InheritedCommands.NameCounter.Counter import Counter
from src.Repository.Counter.Repository.CounterRepository import getCounterDiscordMapping
from src.Repository.DiscordUser.Entity.DiscordUser import DiscordUser

FELIX_COUNTER_MINUTES = 20
FELIX_COUNTER_START_KEYWORD = 'start'
FELIX_COUNTER_STOP_KEYWORD = 'stop'
LIAR = 'https://tenor.com/KoqH.gif'

logger = logging.getLogger("KVGG_BOT")


def getAllKeywords() -> list:
    return [FELIX_COUNTER_START_KEYWORD, FELIX_COUNTER_STOP_KEYWORD]


class FelixCounter(Counter):

    def __init__(self, dcUserDb: DiscordUser = None):
        super().__init__('Felix', dcUserDb)

    def getCounterValue(self) -> int:
        if self.dcUserDb:
            return self.dcUserDb['felix_counter']
        return -1

    async def setCounterValue(self, value: int):
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

    async def updateFelixCounter(self, member: Member, dcUserDb: DiscordUser, session: Session):
        """
        Increases the Felix-Counter of members with an active timer

        :return:
        """
        if not dcUserDb.felix_counter_start:
            logger.debug(f"{dcUserDb.username} has no felix-counter")

            return

        # time to start is not yet reached
        if dcUserDb.felix_counter_start > datetime.now():
            return

        if not (counterDiscordMapping := getCounterDiscordMapping(member, "felix", session)):
            logger.error(f"couldn't fetch CounterDiscordMapping for {member.display_name} and Felix-Counter")

            return

        # timer still active
        if (datetime.now() - dcUserDb.felix_counter_start).seconds // 60 <= 20:
            counterDiscordMapping.value += 1
        else:
            dcUserDb.felix_counter_start = null()

            try:
                await sendDM(member, "Dein Felix-Counter ist ausgelaufen und du hast 20 dazu "
                                     "bekommen! Schade, dass du dich nicht an deine abgemachte Zeit "
                                     "gehalten hast." + separator)
            except Exception as error:
                logger.error(f"couldn't send DM to {member.display_name}", exc_info=error)

    async def checkFelixCounterAndSendStopMessage(self, member: Member, dcUserDb: DiscordUser):
        """
        Check if the given DiscordUser had a Felix-Counter, if so it stops the timer

        :param member: Member of the counter to send the message
        :param dcUserDb: Database user of the member
        :return:
        """
        logger.debug(f"checking Felix-Timer from {dcUserDb}")

        if dcUserDb.felix_counter_start:
            dcUserDb.felix_counter_start = None
        else:
            return

        try:
            await sendDM(member, "Dein Felix-Counter wurde beendet!" + separator)
        except Exception as error:
            logger.error(f"couldn't send DM to {dcUserDb}", exc_info=error)
        else:
            logger.debug(f"informed {dcUserDb} about ending Felix-Counter")
