import logging
from datetime import datetime, timedelta

import discord
from dateutil.relativedelta import relativedelta
from discord import Client, Member
from sqlalchemy import select, insert
from sqlalchemy.orm import Session

from src.DiscordParameters.ExperienceParameter import ExperienceParameter
from src.DiscordParameters.NotificationType import NotificationType
from src.DiscordParameters.QuestParameter import QuestDates
from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Entities.DiscordUser.Repository.NotificationSettingRepository import getNotificationSettings
from src.Entities.Experience.Entity.Experience import Experience
from src.Entities.Experience.Repository.ExperienceRepository import getExperience
from src.Entities.Newsletter.Entity.Newsletter import Newsletter
from src.Entities.Newsletter.Entity.NewsletterDiscordMapping import NewsletterDiscordMapping
from src.Entities.Quest.Entity.Quest import Quest
from src.Entities.Quest.Entity.QuestDiscordMapping import QuestDiscordMapping
from src.Helper.GetFormattedTime import getFormattedTime
from src.Helper.SendDM import sendDM, separator
from src.Id.Categories import UniversityCategory
from src.Manager.DatabaseManager import getSession
from src.Services.ExperienceService import isDoubleWeekend, ExperienceService

logger = logging.getLogger("KVGG_BOT")


class NotificationService:

    def __init__(self, client: Client):
        """
        :param client:
        """
        self.client = client

        self.xpService = ExperienceService(self.client)

    # noinspection PyMethodMayBeStatic
    async def _sendMessage(self,
                           member: Member,
                           content: str,
                           typeOfMessage: NotificationType | None,
                           useSeparator: bool = True, ):
        """
        Sends a DM to the user and handles errors.
        This method also checks if the given user wants that kind of message.

        :param member: C.F. sendDM
        :param content: C.F. sendDM
        :return: Bool about the success of the operation
        """
        if member.bot:
            logger.warning(f"not sending DM to {member.display_name} because it's a bot")

            return

        if typeOfMessage:
            if not (session := getSession()):
                return

            settings = getNotificationSettings(member, session)

            if not settings:
                logger.error(f"no notification settings for {member.display_name}, aborting sending message")

                return
            # convert the setting object to a dict and get the value with the type as a key
            elif not settings.__dict__[typeOfMessage.value] or not settings.notifications:
                logger.debug(f"{member.display_name} does not want to receive {typeOfMessage.value}-messages")

                return

            nameOfSettingType = NotificationType.getSettingNameForType(typeOfMessage)
            content += (f"\n\n`Du kannst diese Art von Benachrichtigungen auf dem Server mit '/notifications "
                        f"{nameOfSettingType.value if nameOfSettingType else '(FEHLER)'}' ein- oder ausschalten.`")

            session.close()
        else:
            content += f"\n\n`Du kannst diese Art von Benachrichtigungen nicht ausschalten.`"

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

    async def informAboutNewQuests(self, member: Member, time: QuestDates, quests: list[QuestDiscordMapping]):
        """
        Informs the member about new quests.

        :param member: Member, who will be notified
        :param time: Type of quest
        :param quests: List of all new quests
        :raise ConnectionError: If the database connection cant be established
        """
        message = f"__**Du hast folgende neue {time.value.capitalize()}-Quests**__:\n\n"

        for quest in quests:
            message += f"- {quest.quest.description}\n"

        message = message.rstrip()

        await self._sendMessage(member, message, NotificationType.QUEST)

    async def sendQuestFinishNotification(self, member: Member, quest: Quest):
        """
        Informs the member about a completed quest.

        :param member: Member, who will be notified
        :param quest: Quest to notify about
        :raise ConnectionError: If the database connection cant be established
        """
        time: str = quest.time_type

        await self._sendMessage(member,
                                f"__**Hey {member.nick if member.nick else member.name}, "
                                f"du hast folgende {time.capitalize()}-Quest geschafft**__:\n\n- "
                                f"{quest.description}\n\n"
                                f"Dafür hast du einen **XP-Boost** erhalten. Schau mal nach!",
                                NotificationType.QUEST, )

    async def runNotificationsForMemberUponJoining(self, member: Member, dcUserDb: DiscordUser, session: Session):
        """
        Sends all opted in notifications and advertisements.

        :param member: Member, who will receive the messages.
        :param dcUserDb: Database user of the member.
        :param session: Database session
        """
        answer = ""

        # don't send any notifications to university users
        if member.voice.channel.category.id in UniversityCategory.getValues():
            return

        answer += await self._welcomeBackMessage(member, dcUserDb, session)

        if (xpAnswer := await self._informAboutDoubleXpWeekend()) != "":
            answer += xpAnswer + separator

        answer += await self._xDaysOfflineMessage(member, dcUserDb)

        # nothing to send
        if answer == "":
            logger.debug(f"no notifications for {member.display_name}")

            return
        else:
            # remove the last separator because it's not needed, but every function adds one
            answer = answer.rstrip(separator)

        await self._sendMessage(member, answer, NotificationType.WELCOME_BACK)

        await self._sendNewsletter(member, dcUserDb, session)

    # noinspection PyMethodMayBeStatic
    async def _sendNewsletter(self, member: Member, dcUserDb: DiscordUser, session: Session):
        """
        Sends the current newsletter(s) to the newly joined member.

        :param member: Member, who will receive the newsletter
        :param dcUserDb: DiscordUser of the member
        :param session: Database session
        """
        answer = ""
        # noinspection PyTypeChecker
        getQuery = (select(Newsletter)
                    .where(Newsletter.id.not_in((select(NewsletterDiscordMapping.newsletter_id)
                                                 .where(NewsletterDiscordMapping.discord_id == dcUserDb.id, )
                                                 .scalar_subquery())),
                           Newsletter.created_at > dcUserDb.created_at,
                           Newsletter.created_at > datetime.now() - relativedelta(months=6), ))

        try:
            newsletters = session.scalars(getQuery).all()
        except Exception as error:
            logger.error(f"couldn't fetch newsletters for {dcUserDb}", exc_info=error)
            session.rollback()

            return ""

        if not newsletters:
            logger.debug(f"no newsletters to send for {dcUserDb}")

            return ""

        answer += "__**NEWSLETTER**__\n\n"

        for newsletter in newsletters:
            insertQuery = insert(NewsletterDiscordMapping).values(newsletter_id=newsletter.id,
                                                                  discord_id=dcUserDb.id,
                                                                  sent_at=datetime.now(), )

            try:
                session.execute(insertQuery)
                session.commit()
            except Exception as error:
                logger.error(f"couldn't insert new NewsletterDiscordMapping for {dcUserDb} and {newsletter}",
                             exc_info=error, )

                # if the query couldn't be run don't send newsletter to member to avoid future spam
                return ""

            answer += (newsletter.message
                       + "\n- vom "
                       + newsletter.created_at.strftime("%d.%m.%Y um %H:%M Uhr")
                       + "\n\n")

        logger.debug(f"sent {len(newsletters)} newsletters to {dcUserDb.username}")
        await self._sendMessage(member, answer.rstrip("\n"), None, )

    async def _welcomeBackMessage(self, member: Member, dcUserDb: DiscordUser, session: Session) -> str:
        """
        Sends a welcome back notification for users who opted in

        :param member: Member, who joined
        :param dcUserDb: Discord User from our database
        :return:
        """
        if not dcUserDb.last_online:
            logger.debug(f"{member.display_name} has no last_online")

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

        lastOnlineDiff: timedelta = now - dcUserDb.last_online
        days: int = lastOnlineDiff.days
        hours: int = lastOnlineDiff.seconds // 3600
        minutes: int = (lastOnlineDiff.seconds // 60) % 60

        if days < 1 and hours < 1 and minutes < 30:
            logger.debug(f"{member.display_name} was online less than 30 minutes ago")

            return ""

        onlineTime: str = getFormattedTime(dcUserDb.time_online)
        streamTime: str = getFormattedTime(dcUserDb.time_streamed)
        universityTime: str = getFormattedTime(dcUserDb.university_time_online)
        xp: Experience | None = getExperience(member, session)

        # circular import
        from src.Services.GameDiscordService import GameDiscordService
        playTime: str | None = GameDiscordService(self.client).getOverallPlayedTime(member, dcUserDb, session)

        try:
            # circular import
            from src.Services.QuestService import QuestService

            questService = QuestService(self.client)
            quests = questService.listQuests(member)
        except Exception as error:
            logger.error("failure to start QuestService", exc_info=error)

            quests = None

        message = (f"Hey, guten {daytime}. Du warst vor {days} Tagen, {hours} Stunden und {minutes} Minuten zuletzt "
                   f"online. ")
        message += f"Deine Online-Zeit beträgt __**{onlineTime} Stunden**__ :telephone:"
        message += f", deine Stream-Zeit __**{streamTime} Stunden**__ :tv:"

        if playTime:
            message += f" und deine Spielzeit __**{playTime} Stunden**__ :video_game:. "
        else:
            message += ". "

        if universityTime:
            message += f"Du hast außerdem __**{universityTime} Stunden**__ :school_satchel: in der Uni verbracht. "

        if xp:
            message += (f"Du hast bereits __**{'{:,}'.format(xp.xp_amount).replace(',', '.')} "
                        f"XP**__ :star2: gefarmt.")

        if quests:
            message += " " + quests

        message += "\n__**Viel Spaß!**__"

        return message + separator

    """You are finally awake GIF"""
    finallyAwake = "https://tenor.com/bwJvI.gif"

    async def _xDaysOfflineMessage(self, member: Member, dcUserDb: DiscordUser) -> str:
        """
        If the member was offline for longer than 30 days, he / she will receive a welcome back message

        :param member: Member, who the condition is tested against
        :param dcUserDb: DiscordUser from the database
        :return: Boolean if a message was sent
        """
        if not dcUserDb.last_online:
            logger.debug(f"{member.display_name} has no last_online status")

            return ""

        if (datetime.now() - dcUserDb.last_online).days >= 14:
            return (f"Schön, dass du mal wieder da bist :) Schau gerne öfters mal wieder vorbei. "
                    f"__**Wir freuen uns auf dich!**__\n\n{self.finallyAwake}{separator}")

        logger.debug(f"{member.display_name} was less than 14 days online ago")

        return ""

    # noinspection PyMethodMayBeStatic
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

    async def sendMemeLikesNotification(self, member: Member, message: str):
        """
        Checks and send the meme likes notification
        """
        await self._sendMessage(member, message, NotificationType.MEME_LIKES)

    async def notifyAboutAcceptedLike(self, member: Member, message: str):
        """
        Sends a message to the member about the accepted like.
        """
        await self._sendMessage(member, message, NotificationType.MEME_LIKES)

    async def informAboutFelixTimer(self, member: Member, message: str):
        """
        Sends a message to the member about the Felix-Counter.
        """
        await self._sendMessage(member, message, None)
