import logging
from datetime import datetime, timedelta

from discord import Client, Member

from src.Helper.SendDM import sendDM
from src.Services.ExperienceService import ExperienceService, isDoubleWeekend

logger = logging.getLogger("KVGG_BOT")


class NotificationService:
    def __init__(self, client: Client):
        self.client = client

    async def runNotificationsForMember(self, member: Member, dcUserDb: dict) -> dict:
        """
        Sends all opted in notifications and advertisements. Returns the maybe edited dcUserDb.

        :param member: Member, who will receive the messages.
        :param dcUserDb: Database user of the member.
        :return: dcUserDb
        """
        dcUserDb = await self.__sendAdvertisement(member, dcUserDb)

        if not await self.__xDaysOfflineMessage(member, dcUserDb):
            await self.__welcomeBackMessage(member, dcUserDb)

        await self.__informAboutDoubleXpWeekend(member, dcUserDb)

        return dcUserDb

    async def __sendAdvertisement(self, member: Member, dcUserDb: dict) -> dict:
        """
        Sends the current advertisement to the newly joined member and returns the edited dcUserDb.

        :param member:
        :param dcUserDb:
        :return:
        """
        try:
            # ad was sent already
            if dcUserDb['received_advertisement_notification']:
                return dcUserDb

            with open("data/advertisement.txt", 'r') as file:
                message = file.read()

            await sendDM(member, message)

            dcUserDb['received_advertisement_notification'] = 1
        except Exception as error:
            logger.error("error while sending advertisement to %s" % member.name, exc_info=error)
        finally:
            return dcUserDb

    async def __welcomeBackMessage(self, member: Member, dcUserDb: dict):
        """
        Sends a welcome back notification for users who opted in

        :param member: Member, who joined
        :param dcUserDb: Discord User from our database
        :return:
        """
        optedIn = dcUserDb['welcome_back_notification']

        if not optedIn or optedIn is False:
            logger.debug("%s is not opted in for welcome_back_notification" % member.name)

            return
        elif not dcUserDb['last_online']:
            logger.debug("%s has no last_online" % member.name)

            return

        now = datetime.now()

        if 0 <= now.hour <= 11:
            daytime = "Morgen"
        elif 12 <= now.hour <= 14:
            daytime = "Mittag"
        elif 15 <= now.hour <= 17:
            daytime = "Nachmittag"
        else:
            daytime = "Abend"

        if not dcUserDb['last_online']:
            return

        lastOnlineDiff: timedelta = now - dcUserDb['last_online']
        days: int = lastOnlineDiff.days
        hours: int = lastOnlineDiff.seconds // 3600
        minutes: int = (lastOnlineDiff.seconds // 60) % 60

        if days < 1 and hours < 1 and minutes < 30:
            logger.debug("%s was online less than 30 minutes ago" % member.name)

            return

        onlineTime: str | None = dcUserDb['formated_time']
        streamTime: str | None = dcUserDb['formatted_stream_time']

        xpService = ExperienceService(self.client)
        xp: dict | None = xpService.getXpValue(dcUserDb)

        message = "Hey, guten %s. Du warst vor %d Tagen, %d Stunden und %d Minuten zuletzt online. " % (
            daytime, days, hours, minutes
        )

        if onlineTime:
            message += "Deine Online-Zeit beträgt %s Stunden" % onlineTime

        if streamTime:
            message += ", deine Stream-Zeit %s Stunden. " % streamTime

        if onlineTime and not streamTime:
            message += ". "

        if xp:
            message += "Außerdem hast du bereits %d XP gefarmt." % xp['xp_amount']

        message += "\n\nViel Spaß!"

        try:
            await sendDM(member, message)
        except Exception as error:
            logger.critical("couldn't send DM to %s" % member.name, exc_info=error)
        else:
            logger.debug("sent dm to %s" % member.name)

    """You are finally awake GIF"""
    finallyAwake = "https://tenor.com/bwJvI.gif"

    async def __xDaysOfflineMessage(self, member: Member, dcUserDb) -> bool:
        """
        If the member was offline for longer than 30 days, he / she will receive a welcome back message

        :param member: Member, who the condition is tested against
        :param dcUserDb: DiscordUser from the database
        :return: Boolean if a message was sent
        """
        if not dcUserDb['last_online']:
            logger.debug("%s has no last_online status" % member.name)

            return False

        if (diff := (datetime.now() - dcUserDb['last_online'])).days >= 14:
            try:
                await sendDM(member, "Schön, dass du mal wieder da bist :)\n\nDu warst seit %d Tagen, %d Stunden "
                                     "und %d Minuten nicht mehr da." %
                             (diff.days, diff.seconds // 3600, (diff.seconds // 60) % 60))
                await sendDM(member, self.finallyAwake)
            except Exception as error:
                logger.error("couldnt send DM(s) to %s" % member.name, exc_info=error)
            else:
                logger.debug("sent dm to %s" % member.name)

            return True

        logger.debug("%s was less than %d days online ago" % (member.name, 30))

        return False

    async def __informAboutDoubleXpWeekend(self, member: Member, dcUserDb: dict):
        """
        Sends a DM to the given user to inform him about the currently active double-xp-weekend

        :param dcUserDb: DiscordUser, who will be informed
        :return:
        """
        if not dcUserDb['double_xp_notification'] or not isDoubleWeekend(datetime.now()):
            return

        try:
            await sendDM(member, "Dieses Wochenende gibt es doppelte XP! Viel Spaß beim farmen.\n\nWenn du diese "
                                 "Benachrichtigung nicht mehr erhalten möchtest, kannst du sie in '#bot-commands'"
                                 "auf dem Server mit '/notifications' de- bzw. aktivieren!")
        except Exception as error:
            logger.error("couldn't send DM to %s" % member.name, exc_info=error)
        else:
            logger.debug("sent double xp notification")
