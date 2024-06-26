from __future__ import annotations

import logging
from datetime import datetime

from discord import Member, Client
from sqlalchemy import null
from sqlalchemy.orm import Session

from src.Entities.Counter.Repository.CounterRepository import getCounterDiscordMapping
from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Entities.DiscordUser.Repository.DiscordUserRepository import getDiscordUserById
from src.Id.GuildId import GuildId
from src.InheritedCommands.NameCounter.Counter import Counter
from src.Manager.NotificationManager import NotificationService

FELIX_COUNTER_MINUTES = 20
FELIX_COUNTER_START_KEYWORD = 'start'
FELIX_COUNTER_STOP_KEYWORD = 'stop'
LIAR = 'https://tenor.com/KoqH.gif'

logger = logging.getLogger("KVGG_BOT")


def getAllKeywords() -> list:
    return [FELIX_COUNTER_START_KEYWORD, FELIX_COUNTER_STOP_KEYWORD]


class FelixCounter(Counter):

    def __init__(self, client: Client, dcUserDb: DiscordUser = None):
        super().__init__('Felix', dcUserDb, client)

        self.notificationService = NotificationService(self.client)

    @DeprecationWarning
    def getCounterValue(self) -> int:
        if self.dcUserDb:
            return self.dcUserDb['felix_counter']
        return -1

    @DeprecationWarning
    async def setCounterValue(self, value: int):
        if self.dcUserDb:
            self.dcUserDb['felix_counter'] = value

    @DeprecationWarning
    def getCounterValueByDifferentDiscordUser(self, dcUserDb) -> int:
        return dcUserDb['felix_counter']

    @DeprecationWarning
    def setFelixTimer(self, date: datetime | None):
        if self.dcUserDb:
            self.dcUserDb['felix_counter_start'] = date

    @DeprecationWarning
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
            logger.debug(f"{dcUserDb.username} has not yet reached the start time of the Felix-Counter")

            return

        if not (counterDiscordMapping := getCounterDiscordMapping(member, "felix", session)):
            logger.error(f"couldn't fetch CounterDiscordMapping for {member.display_name} and Felix-Counter")

            return

        # timer still active
        if (datetime.now() - dcUserDb.felix_counter_start).seconds // 60 <= 20:
            counterDiscordMapping.value += 1

            logger.debug(f"increased Felix-Counter of {dcUserDb.username}")
        else:
            invokerID = dcUserDb.felix_counter_invoker
            dcUserDb.felix_counter_start = null()
            dcUserDb.felix_counter_invoker = null()

            await self.notificationService.informAboutFelixTimer(member, "Dein Felix-Counter ist ausgelaufen und du"
                                                                         " hast 20 dazu bekommen! Schade, dass du "
                                                                         "dich nicht an deine abgemachte Zeit "
                                                                         "gehalten hast.")
            if not invokerID:
                return
            if not (invoker := getDiscordUserById(invokerID, session)):
                logger.error(f"couldn't fetch invoker with id {invokerID}")
                return
            if invoker := self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(int(invoker.user_id)):
                await self.notificationService.sendStatusReport(invoker,
                                                                f"Der Felix-Counter von <@{dcUserDb.user_id}> "
                                                                f"({dcUserDb.username}) "
                                                                f"ist ausgelaufen und er/sie hat 20 dazu "
                                                                f"bekommen! Schade, dass er/sie sich "
                                                                f"nicht an die abgemachte Zeit gehalten "
                                                                f"hat.")
            else:
                logger.error(f"couldn't fetch Member with userId {invoker.id} from guild")

            logger.debug(f"informed {member.display_name} about Felix-Counter ending")

    # noinspection PyMethodMayBeStatic
    async def checkFelixCounterAndSendStopMessage(self, member: Member, dcUserDb: DiscordUser, session: Session):
        """
        Check if the given DiscordUser had a Felix-Counter, if so it stops the timer

        :param member: Member of the counter to send the message
        :param dcUserDb: Database user of the member
        :return:
        """
        logger.debug(f"checking Felix-Timer from {dcUserDb}")

        invokerID = dcUserDb.felix_counter_invoker

        if dcUserDb.felix_counter_start:
            dcUserDb.felix_counter_start = None
            dcUserDb.felix_counter_invoker = None
        else:
            return

        await self.notificationService.informAboutFelixTimer(member, "Dein Felix-Counter wurde beendet!")

        if not invokerID:
            return

        if not (invoker := getDiscordUserById(invokerID, session)):
            logger.error(f"couldn't fetch invoker with id {invokerID}")
            return

        if invoker := self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(int(invoker.user_id)):
            await self.notificationService.sendStatusReport(invoker,
                                                            f"Der Felix-Counter von <@{dcUserDb.user_id}> "
                                                            f"({dcUserDb.username}) wurde beendet, da er/sie einem "
                                                            f"Channel gejoint ist.")
        else:
            logger.error(f"couldn't fetch {invoker} from guild")

        logger.debug(f"informed {dcUserDb} about ending Felix-Counter")
