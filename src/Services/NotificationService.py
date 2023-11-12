import logging
from datetime import datetime, timedelta

from discord import Client, Member

from src.DiscordParameters.ExperienceParameter import ExperienceParameter
from src.DiscordParameters.QuestParameter import QuestDates
from src.Helper.SendDM import sendDM
from src.Id.Categories import UniversityCategory
from src.Services.Database import Database
from src.Services.ExperienceService import ExperienceService, isDoubleWeekend

logger = logging.getLogger("KVGG_BOT")


class NotificationService:
    separator = "\n------------------------------------------------------------------------------------\n"

    def __init__(self, client: Client):
        """
        :param client:
        :raise ConnectionError:
        """
        self.client = client
        self.database = Database()

    async def informAboutXpBoostInventoryLength(self, member: Member, currentAmount: int):
        """
        Informs the user about the state of his XP-Inventory.

        :param member: Member to inform and the inventory belongs to
        :param currentAmount: Currently saved Boosts in the inventory
        """
        if currentAmount >= ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value:
            message = ("**Dein XP-Boost-Inventar ist voll!**\n\nDu kannst ab jetzt keine weiteren Boosts in dein "
                       "Inventar aufnehmen, bis du welche benutzt.")
        elif currentAmount >= 25:
            message = (f"**Achtung, dein XP-Boost-Inventar ist fast voll!**\n\nDu kannst noch "
                       f"{ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value - currentAmount} XP-Boost in dein "
                       f"Inventar aufnehmen. Danach ist es nicht mehr möglich welche zu bekommen! Also benutz besser "
                       f"welche.")
        else:
            return

        await sendDM(member, message + self.separator)

    async def informAboutNewQuests(self, member: Member, time: QuestDates, quests: list[dict]):
        """
        Informs the member about new quests.

        :param member: Member, who will be notified
        :param time: Type of quest
        :param quests: List of all new quests
        """
        message = f"__**Du hast folgende neue {time.value.capitalize()}-Quests**__:\n\n"

        for quest in quests:
            message += f"- {quest['description']}\n"

        message = message.rstrip()
        message += self.separator

        await sendDM(member, message)

    async def sendQuestFinishNotification(self, member: Member, questId: int):
        """
        Informs the member about a completed quest.

        :param member: Member, who will be notified
        :param questId: Primary-Key of the completed quest
        """
        query = "SELECT description, time_type FROM quest WHERE id = %s"

        if not (quest := self.database.fetchOneResult(query, (questId,))):
            logger.error("couldn't fetch data from database")

            return

        time: str = quest['time_type']

        await sendDM(member, f"__**Hey {member.nick if member.nick else member.name}, "
                             f"du hast folgende {time.capitalize()}-Quest geschafft**__:\n\n- "
                             f"{quest['description']}\n\n"
                             f"Dafür hast du einen **XP-Boost** erhalten. Schau mal nach!"
                             f"{self.separator}")

    async def runNotificationsForMember(self, member: Member, dcUserDb: dict):
        """
        Sends all opted in notifications and advertisements.

        :param member: Member, who will receive the messages.
        :param dcUserDb: Database user of the member.
        """
        answer = self.separator

        # don't send any notifications to university users
        if member.voice.channel.category.id in UniversityCategory.getValues():
            return

        answer += await self.__sendNewsletter(dcUserDb)

        if not await self.__xDaysOfflineMessage(member, dcUserDb):
            answer += await self.__welcomeBackMessage(member, dcUserDb)

        answer += await self.__informAboutDoubleXpWeekend(dcUserDb)

        # nothing to send
        if answer == self.separator:
            return

        try:
            await sendDM(member, answer)
        except Exception as error:
            logger.error(f"couldn't send DM to {member.name}", exc_info=error)

    async def __sendNewsletter(self, dcUserDb: dict) -> str:
        """
        Sends the current newsletter(s) to the newly joined member.

        :param dcUserDb:
        :return:
        """
        answer = ""

        query = ("SELECT n.* "
                 "FROM newsletter n "
                 "WHERE n.id NOT IN "
                 "(SELECT newsletter_id "
                 "FROM newsletter_discord_mapping "
                 "WHERE discord_id = %s) "
                 "AND n.created_at > %s")

        newsletters = self.database.fetchAllResults(query, (dcUserDb['id'], dcUserDb['created_at'],))

        if not newsletters:
            return ""

        answer += "__**NEWSLETTER**__\n\n"

        for newsletter in newsletters:
            query = ("INSERT INTO newsletter_discord_mapping (newsletter_id, discord_id, sent_at) "
                     "VALUES (%s, %s, %s)")

            # if the query couldn't be run don't send newsletter to member to avoid future spam
            if not self.database.runQueryOnDatabase(query, (newsletter['id'], dcUserDb['id'], datetime.now(),)):
                return ""

            answer += (newsletter['message']
                       + "\n- vom "
                       + newsletter['created_at'].strftime("%d.%m.%Y um %H:%M Uhr")
                       + "\n\n")

        # remove last (two) newlines to return a clean string (end)
        answer.rstrip("\n")

        return answer + self.separator

    async def __welcomeBackMessage(self, member: Member, dcUserDb: dict) -> str:
        """
        Sends a welcome back notification for users who opted in

        :param member: Member, who joined
        :param dcUserDb: Discord User from our database
        :return:
        """
        optedIn = dcUserDb['welcome_back_notification']

        if not optedIn or optedIn is False:
            logger.debug("%s is not opted in for welcome_back_notification" % member.name)

            return ""
        elif not dcUserDb['last_online']:
            logger.debug("%s has no last_online" % member.name)

            return ""

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
            return ""

        lastOnlineDiff: timedelta = now - dcUserDb['last_online']
        days: int = lastOnlineDiff.days
        hours: int = lastOnlineDiff.seconds // 3600
        minutes: int = (lastOnlineDiff.seconds // 60) % 60

        if days < 1 and hours < 1 and minutes < 30:
            logger.debug("%s was online less than 30 minutes ago" % member.name)

            return ""

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

        return message + self.separator

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

    async def __informAboutDoubleXpWeekend(self, dcUserDb: dict) -> str:
        """
        Sends a DM to the given user to inform him about the currently active double-xp-weekend

        :param dcUserDb: DiscordUser, who will be informed
        :return:
        """
        if not dcUserDb['double_xp_notification'] or not isDoubleWeekend(datetime.now()):
            return ""

        return ("Dieses Wochenende gibt es doppelte XP! Viel Spaß beim farmen.\n\nWenn du diese "
                "Benachrichtigung nicht mehr erhalten möchtest, kannst du sie in '#bot-commands'"
                "auf dem Server mit '/notifications' de- bzw. aktivieren!") + self.separator
