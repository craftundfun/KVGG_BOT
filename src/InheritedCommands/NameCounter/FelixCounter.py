from __future__ import annotations

import logging
from datetime import datetime

from discord import Client, Member

from src.Helper.SendDM import sendDM
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Id.GuildId import GuildId
from src.InheritedCommands.NameCounter.Counter import Counter
from src.Services.Database import Database

FELIX_COUNTER_MINUTES = 20
FELIX_COUNTER_START_KEYWORD = 'start'
FELIX_COUNTER_STOP_KEYWORD = 'stop'
LIAR = 'https://tenor.com/KoqH.gif'

logger = logging.getLogger("KVGG_BOT")


def getAllKeywords() -> list:
    return [FELIX_COUNTER_START_KEYWORD, FELIX_COUNTER_STOP_KEYWORD]


class FelixCounter(Counter):

    def __init__(self, dcUserDb: dict = None):
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

    async def updateFelixCounter(self, client: Client):
        """
        Increases the Felix-Counter of members with an active timer

        :param client:
        :return:
        """
        try:
            database = Database()
        except ConnectionError as error:
            logger.error("couldn't connect to MySQL, aborting task", exc_info=error)

            return

        query = "SELECT * FROM discord WHERE felix_counter_start IS NOT NULL"
        dcUsersDb = database.fetchAllResults(query)

        if not dcUsersDb:
            logger.debug("no felix-counter to increase")

            return

        for dcUserDb in dcUsersDb:
            # time to start is not yet reached
            if dcUserDb['felix_counter_start'] > datetime.now():
                continue
            print((datetime.now() - dcUserDb['felix_counter_start']).seconds // 60)
            # timer still active
            if (datetime.now() - dcUserDb['felix_counter_start']).seconds // 60 <= 2:
                dcUserDb['felix_counter'] = dcUserDb['felix_counter'] + 1
            else:
                dcUserDb['felix_counter_start'] = None

                member = client.get_guild(GuildId.GUILD_KVGG.value).get_member(int(dcUserDb['user_id']))

                if member:
                    try:
                        await sendDM(member, "Dein Felix-Counter ist ausgelaufen und du hast 20 dazu "
                                             "bekommen! Schade, dass du dich nicht an deine abgemachte Zeit "
                                             "gehalten hast.")
                    except Exception as error:
                        logger.debug("couldn't send DM to %s" % member.name, exc_info=error)

            query, nones = writeSaveQuery('discord', dcUserDb['id'], dcUserDb)

            if not database.runQueryOnDatabase(query, nones):
                logger.critical("couldn't save changes for %s" % dcUserDb['username'])

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
            await sendDM(member, "Dein Felix-Counter wurde beendet!")
        except Exception as error:
            logger.error("couldn't send DM to %s" % member.name, exc_info=error)
        else:
            logger.debug("sent DM to %s" % member.name)
