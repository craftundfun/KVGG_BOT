from __future__ import annotations

import logging
from datetime import datetime

from discord import Member

from src.Helper.SendDM import sendDM, separator
from src.InheritedCommands.NameCounter.Counter import Counter
from src.Repository.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Services.Database_Old import Database_Old

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

    # TODO increase counter in correct table
    async def updateFelixCounter(self, member: Member, dcUserDb: dict):
        """
        Increases the Felix-Counter of members with an active timer

        :raise ConnectionError: If there is a problem with the database connection
        :return:
        """
        if not dcUserDb['felix_counter_start']:
            logger.debug(f"{dcUserDb['username']} has no felix-counter")

            return

        # time to start is not yet reached
        if dcUserDb['felix_counter_start'] > datetime.now():
            return

        database = Database_Old()

        query = "SELECT * FROM counter WHERE name like 'felix'"
        felixCounter = database.fetchOneResult(query)

        if felixCounter is None:
            logger.error('felixCounter wurde nicht gefunden')

        query = "SELECT * FROM counter_discord_mapping WHERE counter_id = %s AND discord_id = %s"

        if not (felixCounterUser := database.fetchOneResult(query, (felixCounter['id'], dcUserDb['id']))):
            query = "INSERT INTO counter_discord_mapping (counter_id, discord_id, value) VALUES (%s, %s, %s)"
            database.runQueryOnDatabase(query, (felixCounter['id'], dcUserDb['id'], 0))
            felixCounterValue = 0
        else:
            felixCounterValue = felixCounterUser['value']

        # timer still active
        if (datetime.now() - dcUserDb['felix_counter_start']).seconds // 60 <= 20:
            query = "UPDATE counter_discord_mapping SET value = %s WHERE counter_id = %s AND discord_id = %s"
            database.runQueryOnDatabase(query, (felixCounterValue + 1, felixCounter['id'], dcUserDb['id']))
        else:
            dcUserDb['felix_counter_start'] = None

            try:
                await sendDM(member, "Dein Felix-Counter ist ausgelaufen und du hast 20 dazu "
                                     "bekommen! Schade, dass du dich nicht an deine abgemachte Zeit "
                                     "gehalten hast.")
            except Exception as error:
                logger.error("couldn't send DM to %s" % member.name, exc_info=error)

    async def checkFelixCounterAndSendStopMessage(self, member: Member, dcUserDb: dict):
        """
        Check if the given DiscordUser had a Felix-Counter, if so it stops the timer

        :param member: Member of the counter to send the message
        :param dcUserDb: Database user of the member
        :return:
        """
        logger.debug("checking Felix-Timer from %s" % dcUserDb['username'])

        if dcUserDb['felix_counter_start'] is not None:
            dcUserDb['felix_counter_start'] = None
        else:
            return

        try:
            await sendDM(member, "Dein Felix-Counter wurde beendet!" + separator)
        except Exception as error:
            logger.error("couldn't send DM to %s" % member.name, exc_info=error)
        else:
            logger.debug("sent DM to %s" % member.name)
