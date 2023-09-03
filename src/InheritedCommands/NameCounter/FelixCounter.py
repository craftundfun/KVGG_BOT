from __future__ import annotations

import logging
from datetime import datetime, timedelta

from discord import Client, Member

from src.Helper.CreateNewDatabaseConnection import getDatabaseConnection
from src.Helper.SendDM import sendDM
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Id.GuildId import GuildId
from src.InheritedCommands.NameCounter.Counter import Counter

FELIX_COUNTER_MINUTES = 20
FELIX_COUNTER_START_KEYWORD = 'start'
FELIX_COUNTER_STOP_KEYWORD = 'stop'
LIAR = 'https://tenor.com/KoqH.gif'

logger = logging.getLogger("KVGG_BOT")


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

    async def updateFelixCounter(self, client: Client):
        """
        Increases the Felix-Counter of members with an active timer

        :param client:
        :return:
        """
        databaseConnection = getDatabaseConnection()

        if not databaseConnection:
            logger.critical("no database connection!")

            return

        with databaseConnection.cursor() as cursor:
            query = "SELECT * FROM discord WHERE felix_counter_start IS NOT NULL"

            cursor.execute(query)

            if not (data := cursor.fetchall()):
                logger.debug("no felix-counter to increase")

                return

            dcUsersDb = [dict(zip(cursor.column_names, date)) for date in data]

            for dcUserDb in dcUsersDb:
                # timer still active
                if (dcUserDb['felix_counter_start'] + timedelta(minutes=FELIX_COUNTER_MINUTES)) >= datetime.now():
                    dcUserDb['felix_counter'] = dcUserDb['felix_counter'] + 1
                else:
                    dcUserDb['felix_counter_start'] = None

                    member = client.get_guild(int(GuildId.GUILD_KVGG.value)).get_member(int(dcUserDb['user_id']))

                    if member:
                        try:
                            await sendDM(member, "Dein Felix-Counter ist ausgelaufen und du hast 20 dazu "
                                                 "bekommen! Schade, dass du dich nicht an deine abgemachte Zeit "
                                                 "gehalten hast.")
                        except:
                            logger.debug("couldnt send DM to %s" % member.name)

                query, nones = writeSaveQuery('discord', dcUserDb['id'], dcUserDb)

                cursor.execute(query, nones)
            databaseConnection.commit()

    async def checkFelixCounterAndSendStopMessage(self, member: Member, dcUserDb: dict):
        """
        Check if the given DiscordUser had a Felix-Counter, if so it stops the timer

        :param member: Member of the counter to send the message
        :param dcUserDb: Database user of the member
        :return:
        """
        logger.debug("Checking Felix-Timer from %s" % dcUserDb['username'])

        if dcUserDb['felix_counter_start'] is not None:
            dcUserDb['felix_counter_start'] = None
        else:
            return

        try:
            await sendDM(member, "Dein Felix-Counter wurde beendet!")
        except Exception as error:
            logger.error("couldnt send DM to %s" % member.name, exc_info=error)
        else:
            logger.debug("sent dm to %s" % member.name)
