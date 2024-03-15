import logging
from datetime import datetime, timedelta

import discord
from discord import Client, Member

from src.DiscordParameters.ExperienceParameter import ExperienceParameter
from src.DiscordParameters.NotificationType import NotificationType
from src.DiscordParameters.QuestParameter import QuestDates
from src.Helper.SendDM import sendDM, separator
from src.Id.Categories import UniversityCategory
from src.Repository.NotificationSettingRepository import getNotificationSettings
from src.Services.Database_Old import Database_Old
from src.Services.ExperienceService import isDoubleWeekend, ExperienceService

logger = logging.getLogger("KVGG_BOT")


class NotificationService:

    def __init__(self, client: Client):
        """
        :param client:
        """
        self.client = client

        self.xpService = ExperienceService(self.client)

    async def _sendMessage(self, member: Member,
                           content: str,
                           typeOfMessage: NotificationType,
                           useSeparator: bool = True):
        """
        Sends a DM to the user and handles errors.
        This method also checks if the given user wants that kind of message.

        :param member: C.F. sendDM
        :param content: C.F. sendDM
        :return: Bool about the success of the operation
        """
        settings = getNotificationSettings(member, Database_Old())

        if not settings:
            logger.critical(f"no notification settings for {member.display_name}, aborting sending message")

            return
        elif not settings[typeOfMessage.value] or not settings['notifications']:
            logger.debug(f"{member.display_name} does not want to receive {typeOfMessage.value}-messages")

            return

        nameOfSettingType = NotificationType.getSettingNameForType(typeOfMessage)
        content += (f"\n\n`Du kannst diese Art von Benachrichtigungen auf dem Server mit '/notifications "
                    f"{nameOfSettingType.value if nameOfSettingType else '(FEHLER)'}' ein- oder ausschalten.`")

        if useSeparator:
            content += separator

        try:
            await sendDM(member, content)
        except discord.Forbidden:
            logger.warning(f"couldn't send DM to {member.name}: Forbidden")
        except Exception as error:
            logger.error(f"couldn't send DM to {member.name}", exc_info=error)

    async def informAboutXpBoostInventoryLength(self, member: Member, currentAmount: int):
        """
        Informs the user about the state of his XP-Inventory.

        :param member: Member to inform and the inventory belongs to
        :param currentAmount: Currently saved Boosts in the inventory
        """
        if currentAmount >= ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value:
            message = ("**Dein XP-Boost-Inventar ist voll!**\n\nDu kannst ab jetzt keine weiteren Boosts in dein "
                       "Inventar aufnehmen, bis du welche benutzt.")
        elif currentAmount >= (ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value - 5):
            message = (f"**Achtung, dein XP-Boost-Inventar ist fast voll!**\n\nDu kannst noch "
                       f"{ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value - currentAmount} XP-Boost in dein "
                       f"Inventar aufnehmen. Danach ist es nicht mehr möglich welche zu bekommen! Also benutz besser "
                       f"welche.")
        else:
            return

        await self._sendMessage(member, message, NotificationType.XP_INVENTORY)

    async def informAboutNewQuests(self, member: Member, time: QuestDates, quests: list[dict]):
        """
        Informs the member about new quests.

        :param member: Member, who will be notified
        :param time: Type of quest
        :param quests: List of all new quests
        :raise ConnectionError: If the database connection cant be established
        """
        message = f"__**Du hast folgende neue {time.value.capitalize()}-Quests**__:\n\n"

        for quest in quests:
            message += f"- {quest['description']}\n"

        message = message.rstrip()

        await self._sendMessage(member, message, NotificationType.QUEST)

    async def sendQuestFinishNotification(self, member: Member, questId: int):
        """
        Informs the member about a completed quest.

        :param member: Member, who will be notified
        :param questId: Primary-Key of the completed quest
        :raise ConnectionError: If the database connection cant be established
        """
        database = Database_Old()
        query = "SELECT description, time_type FROM quest WHERE id = %s"

        if not (quest := database.fetchOneResult(query, (questId,))):
            logger.error("couldn't fetch data from database")

            return

        time: str = quest['time_type']

        await self._sendMessage(member, f"__**Hey {member.nick if member.nick else member.name}, "
                                        f"du hast folgende {time.capitalize()}-Quest geschafft**__:\n\n- "
                                        f"{quest['description']}\n\n"
                                        f"Dafür hast du einen **XP-Boost** erhalten. Schau mal nach!",
                                NotificationType.QUEST)

    async def runNotificationsForMember(self, member: Member, dcUserDb: dict):
        """
        Sends all opted in notifications and advertisements.

        :param member: Member, who will receive the messages.
        :param dcUserDb: Database user of the member.
        :raise ConnectionError: If the database connection cant be established
        """
        answer = ""

        # don't send any notifications to university users
        if member.voice.channel.category.id in UniversityCategory.getValues():
            return

        canSendWelcomeBackMessage = await self._xDaysOfflineMessage(member, dcUserDb)
        answer += await self._sendNewsletter(dcUserDb)

        if not canSendWelcomeBackMessage:
            answer += await self._welcomeBackMessage(member, dcUserDb)

        if (xpAnswer := await self._informAboutDoubleXpWeekend()) != "":
            # if no welcome message is there to avoid leading seperator
            if answer != "":
                answer += separator
            answer += xpAnswer

        # nothing to send
        if answer == "":
            return

        await self._sendMessage(member, answer, NotificationType.WELCOME_BACK)

    async def _sendNewsletter(self, dcUserDb: dict) -> str:
        """
        Sends the current newsletter(s) to the newly joined member.

        :param dcUserDb:
        :return:
        """
        answer = ""
        database = Database_Old()

        query = ("SELECT n.* "
                 "FROM newsletter n "
                 "WHERE n.id NOT IN "
                 "(SELECT newsletter_id "
                 "FROM newsletter_discord_mapping "
                 "WHERE discord_id = %s) "
                 "AND n.created_at > %s")

        newsletters = database.fetchAllResults(query, (dcUserDb['id'], dcUserDb['created_at'],))

        if not newsletters:
            return ""

        answer += "__**NEWSLETTER**__\n\n"

        for newsletter in newsletters:
            query = ("INSERT INTO newsletter_discord_mapping (newsletter_id, discord_id, sent_at) "
                     "VALUES (%s, %s, %s)")

            # if the query couldn't be run don't send newsletter to member to avoid future spam
            if not database.runQueryOnDatabase(query, (newsletter['id'], dcUserDb['id'], datetime.now(),)):
                return ""

            answer += (newsletter['message']
                       + "\n- vom "
                       + newsletter['created_at'].strftime("%d.%m.%Y um %H:%M Uhr")
                       + "\n\n")

        # remove last (two) newlines to return a clean string (end)
        answer.rstrip("\n")

        return answer + separator

    async def _welcomeBackMessage(self, member: Member, dcUserDb: dict) -> str:
        """
        Sends a welcome back notification for users who opted in

        :param member: Member, who joined
        :param dcUserDb: Discord User from our database
        :return:
        """
        if not dcUserDb['last_online']:
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

        lastOnlineDiff: timedelta = now - dcUserDb['last_online']
        days: int = lastOnlineDiff.days
        hours: int = lastOnlineDiff.seconds // 3600
        minutes: int = (lastOnlineDiff.seconds // 60) % 60

        if days < 1 and hours < 1 and minutes < 30:
            logger.debug("%s was online less than 30 minutes ago" % member.name)

            return ""

        onlineTime: str | None = dcUserDb['formated_time']
        streamTime: str | None = dcUserDb['formatted_stream_time']
        xp: dict | None = self.xpService.getXpValue(dcUserDb)

        try:
            # circular import
            from src.Services.QuestService import QuestService

            questService = QuestService(self.client)
            quests = questService.listQuests(member)
        except ConnectionError as error:
            logger.error("failure to start QuestService", exc_info=error)
            quests = None

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

        if quests:
            message += " " + quests

        message += "\n\nViel Spaß!"

        return message

    """You are finally awake GIF"""
    finallyAwake = "https://tenor.com/bwJvI.gif"

    async def _xDaysOfflineMessage(self, member: Member, dcUserDb: dict) -> bool:
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
            await self._sendMessage(member,
                                    "Schön, dass du mal wieder da bist :)\n\nDu warst seit %d Tagen, %d Stunden "
                                    "und %d Minuten nicht mehr da." %
                                    (diff.days, diff.seconds // 3600, (diff.seconds // 60) % 60),
                                    NotificationType.WELCOME_BACK)
            await self._sendMessage(member, self.finallyAwake, NotificationType.WELCOME_BACK, False)
            # use seperator here so the meme will be an embed => maybe solve that better in the future
            await self._sendMessage(member, separator, NotificationType.WELCOME_BACK, False)

            return True

        logger.debug("%s was less than %d days online ago" % (member.name, 30))

        return False

    async def _informAboutDoubleXpWeekend(self) -> str:
        """
        Sends a DM to the given user to inform him about the currently active double-xp-weekend

        :return:
        """
        if not isDoubleWeekend(datetime.now()):
            return ""

        return "Dieses Wochenende gibt es doppelte XP! Viel Spaß beim farmen."

    async def notifyAboutUnfinishedQuests(self, questDate: QuestDates, quests: list, member: Member):
        """
        Sends a message to the member about the unfinished quests.
        """
        message = (f"Hey {member.display_name}, du hast noch folgende {questDate.value.capitalize()}-Quests "
                   f"nicht abgeschlossen:\n\n")

        for index, quest in enumerate(quests, 1):
            message += (f"{index}. {quest.description} Aktueller Wert: **{quest['current_value']}**, "
                        f"von: {quest['value_to_reach']} {quest['unit']}\n")

        message = message.rstrip()

        await self._sendMessage(member, message, NotificationType.QUEST)

    async def sendStatusReport(self, member: Member, message: str):
        """
        Checks and sends status reports to the given user.

        :param member: The member who will receive the message
        :param message: The message (status report) to send
        """
        await self._sendMessage(member, message, NotificationType.STATUS)

    async def sendRetrospect(self, member: Member, message: str):
        """
        Checks and sends the retrospect to the given user.

        :param member: The member who will receive the message
        :param message: The message (status report) to send
        """
        await self._sendMessage(member, message, NotificationType.RETROSPECT)

    async def sendXpSpinNotification(self, member: Member, message: str):
        """
        Checks and send the xp-spin reminder
        """
        await self._sendMessage(member, message, NotificationType.XP_SPIN)
