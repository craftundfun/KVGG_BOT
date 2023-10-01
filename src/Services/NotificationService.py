import logging
from datetime import datetime, timedelta

from discord import Client, Member

from src.Helper.SendDM import sendDM
from src.Id.ChannelIdUniversityTracking import ChannelIdUniversityTracking
from src.Services.Database import Database
from src.Services.ExperienceService import ExperienceService, isDoubleWeekend

logger = logging.getLogger("KVGG_BOT")


class NotificationService:
    def __init__(self, client: Client):
        """
        :param client:
        :raise ConnectionError:
        """
        self.client = client
        self.database = Database()

    async def runNotificationsForMember(self, member: Member, dcUserDb: dict):
        """
        Sends all opted in notifications and advertisements. Returns the maybe edited dcUserDb.

        :param member: Member, who will receive the messages.
        :param dcUserDb: Database user of the member.
        :return: dcUserDb
        """
        # don't send any notifications to university users
        if member.voice.channel.id in ChannelIdUniversityTracking.getValues():
            return

        await self.__sendNewsletter(member, dcUserDb)

        if not await self.__xDaysOfflineMessage(member, dcUserDb):
            await self.__welcomeBackMessage(member, dcUserDb)

        await self.__informAboutDoubleXpWeekend(member, dcUserDb)

    async def __sendNewsletter(self, member: Member, dcUserDb: dict):
        """
        Sends the current newsletter(s) to the newly joined member.

        :param member:
        :param dcUserDb:
        :return:
        """
        query = ("SELECT n.* "
                 "FROM newsletter n "
                 "WHERE n.id NOT IN "
                 "(SELECT newsletter_id "
                 "FROM newsletter_discord_mapping "
                 "WHERE discord_id = %s) "
                 "AND n.created_at > %s")

        newsletters = self.database.fetchAllResults(query, (dcUserDb['id'], dcUserDb['created_at'],))

        if not newsletters:
            return

        try:
            await sendDM(member, "__**NEWSLETTER**__")
        except Exception as error:
            logger.error("couldn't send DM to %s" % member.name, exc_info=error)

        for newsletter in newsletters:
            query = ("INSERT INTO newsletter_discord_mapping (newsletter_id, discord_id, sent_at) "
                     "VALUES (%s, %s, %s)")

            if not self.database.runQueryOnDatabase(query,
                                                    (newsletter['id'], dcUserDb['id'], datetime.now(),)):
                # if the query couldn't be run don't send newsletter to member to avoid future spam
                return

            try:
                await sendDM(member,
                             newsletter['message'] + "\n- vom "
                             + newsletter['created_at'].strftime("%d.%m.%Y um %H:%M Uhr"))
            except Exception as error:
                logger.error("couldn't sent DM to %s" % member.name, exc_info=error)

                continue

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

        try:
            xpService = ExperienceService(self.client)
        except ConnectionError as error:
            logger.error("failure to start ExperienceService", exc_info=error)

            xp = None
        else:
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
            message += "Außerdem hast du bereits %s XP gefarmt." % '{:,}'.format(xp['xp_amount']).replace(',', '.')

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
                logger.error("couldn't send DM(s) to %s" % member.name, exc_info=error)
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
