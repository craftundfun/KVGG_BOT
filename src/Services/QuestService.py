import asyncio
import copy
import logging
import random
from datetime import datetime
from enum import Enum

from discord import Client, Member, Message
from sqlalchemy import select, null, insert, delete
from sqlalchemy.orm import Session

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.DiscordParameters.QuestParameter import QuestDates
from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Entities.DiscordUser.Repository.DiscordUserRepository import getDiscordUser
from src.Entities.Quest.Entity.Quest import Quest
from src.Entities.Quest.Entity.QuestDiscordMapping import QuestDiscordMapping
from src.Entities.Quest.Repository.QuestDiscordMappingRepository import getQuestDiscordMapping
from src.Id.GuildId import GuildId
from src.Manager.DatabaseManager import getSession
from src.Manager.NotificationManager import NotificationService
from src.Services.ExperienceService import ExperienceService

logger = logging.getLogger("KVGG_BOT")
lock = asyncio.Lock()


class QuestType(Enum):
    MESSAGE_COUNT = "message_count"
    COMMAND_COUNT = "command_count"
    ONLINE_TIME = "online_time"
    STREAM_TIME = "stream_time"
    DAYS_ONLINE = "days_online"
    ONLINE_STREAK = "online_streak"
    MEME_COUNT = "meme_count"
    ACTIVITY_TIME = "activity_time"


class QuestService:
    questAccomplished = "✅"
    questNotAccomplished = "❌"

    def __init__(self, client: Client):
        self.client = client

        self.notificationService = NotificationService(self.client)
        self.experienceService = ExperienceService(self.client)

    async def addProgressToQuest(self, member: Member, questType: QuestType, value: int = 1, message: Message = None):
        """
        Based on the type of quest, the member will earn progress for this quest.

        :param member: Member, whose quests will be checked
        :param questType: Type of quest
        :param value: Optional value to overwrite the standard increase of one
        :param message: Optional message for extra checks; needed for message_count
        """
        if not (session := getSession()):
            return

        # create new quests if necessary - dirty, but easy
        if not getQuestDiscordMapping(member, session):
            logger.error(f"couldn't fetch quests for {member.display_name}")

            return

        # noinspection PyTypeChecker
        getQuery = (select(QuestDiscordMapping)
                    .where(QuestDiscordMapping.quest_id.in_(select(Quest.id)
                                                            .where(Quest.type == questType.value)
                                                            .scalar_subquery()),
                           QuestDiscordMapping.discord_id == (select(DiscordUser.id)
                                                              .where(DiscordUser.user_id == str(member.id))
                                                              .scalar_subquery()), ))

        # use lock here to avoid giving spammers more boosts
        async with lock:
            try:
                quests = session.scalars(getQuery).all()
            except Exception as error:
                logger.error("failure to fetch quests from database", exc_info=error)
                session.close()

                return

            for quest in quests:
                lastUpdated: datetime | None = quest.time_updated

                # special checks for special quests
                if questType == QuestType.DAYS_ONLINE:
                    # if its same day the count cant be increased
                    if lastUpdated and lastUpdated.day == datetime.now().day:
                        logger.debug(f"lastUpdated: {lastUpdated.day} == now: {datetime.now().day} for {member.name}, "
                                     f"continuing loop")

                        continue
                    else:
                        logger.debug(f"no lastUpdated or lastUpdated: {lastUpdated.day if lastUpdated else 'None'} "
                                     f"== current day, continuing to give value")

                elif questType == QuestType.ONLINE_STREAK:
                    # if its same day the count cant be increased
                    if lastUpdated and datetime.now().day == lastUpdated.day:
                        logger.debug(f"lastUpdated: {lastUpdated.day} == now: {datetime.now().day} for {member.name}, "
                                     f"continuing loop")

                        continue
                    else:
                        logger.debug(f"no lastUpdated or lastUpdated: {lastUpdated.day if lastUpdated else 'None'} "
                                     f"== current day, continuing to give value")

                    # if the difference is too big, the progress will be lost
                    if lastUpdated and datetime.now().day - lastUpdated.day > 1:
                        # if the streak was broken and the value fulfilled, don't reset to zero and continue
                        if quest.current_value >= quest.quest.value_to_reach:
                            logger.debug("streak broken, saving current state")

                            continue

                        # reset value due to loss in streak
                        quest.current_value = 0
                        quest.time_updated = null()

                        try:
                            session.commit()
                        except Exception as error:
                            logger.error(f"failure to save quest_discord_mapping to database: {quest}",
                                         exc_info=error, )
                            session.rollback()

                        continue

                elif questType == QuestType.MESSAGE_COUNT:
                    if not message:
                        logger.error("message is needed for message_count quest")

                        return

                    if not quest.additional_info:
                        additionalInfo = []
                    else:
                        additionalInfo = copy.deepcopy(quest.additional_info)

                    additionalInfo.append(message.id)
                    logger.debug(f"inserted message id into additional_info for message_count quest for "
                                 f"{member.display_name}")

                quest.current_value += value
                quest.time_updated = datetime.now()

                await self._checkForFinishedQuest(member, quest)

                try:
                    session.commit()
                except Exception as error:
                    logger.error(f"failure to save quest_discord_mapping to database: {quest}",
                                 exc_info=error, )
                    session.rollback()

            session.close()

    async def runGrantCheckForMessageQuest(self, member: Member):
        pass

    async def _checkForFinishedQuest(self, member: Member, qdm: QuestDiscordMapping):
        """
        If a quest was finished a xp-boost will be given to the user.

        :param member: Member, who completed the quest and will get the boost
        :param qdm: QuestDiscordMapping
        """
        if qdm.current_value == qdm.quest.value_to_reach:
            if qdm.quest.type == QuestType.MESSAGE_COUNT.value:
                await self.notificationService.informAboutPartlyFinishedQuest(member, qdm.quest)
                logger.debug(f"informed {member.display_name} about partly quest finish")

                return

            await self.notificationService.sendQuestFinishNotification(member, qdm.quest)

            if qdm.quest.time_type == "daily":
                boost = AchievementParameter.DAILY_QUEST
            elif qdm.quest.time_type == "weekly":
                boost = AchievementParameter.WEEKLY_QUEST
            else:
                boost = AchievementParameter.MONTHLY_QUEST

            await self.experienceService.grantXpBoost(member, boost)

    async def resetQuests(self, time: QuestDates):
        """
        Resets all the quest from the given time and creates new ones for members who are currently online.

        :param time: Time to reset the quests and create new ones
        """
        if not (session := getSession()):
            return

        deleteQuery = (delete(QuestDiscordMapping)
                       .where(QuestDiscordMapping.quest_id.in_(select(Quest.id)
                                                               .where(Quest.time_type == time.value)
                                                               .scalar_subquery())))
        try:
            session.execute(deleteQuery)
            session.commit()
        except Exception as error:
            logger.error("couldn't delete quests from database", exc_info=error)
            session.rollback()
            session.close()

            return
        else:
            logger.debug(f"deleted {time.value}-quests")

        await self._createQuestsForAllUsers(time, session)

    async def _informMemberAboutNewQuests(self,
                                          member: Member,
                                          time: QuestDates,
                                          session: Session):
        """
        Fetches all current quests from the given time and informs user about them.

        :param member: Member, who will be informed
        :param time: Type of quests
        :param session:
        """
        # if the member is not online
        if not member.voice:
            return

        if not (quests := getQuestDiscordMapping(member, session)):
            logger.error(f"couldn't fetch quests for {member.display_name}")

            return

        await self.notificationService.informAboutNewQuests(member,
                                                            time,
                                                            # collect only quests from the given time
                                                            [quest for quest in quests if
                                                             quest.quest.time_type == time.value], )

    async def _createQuestsForAllUsers(self, time: QuestDates, session: Session):
        """
        Creates new quests for all online users, so they have new ones right at zero 'o clock.

        :param time: Type of quests
        """
        members = self.client.get_guild(GuildId.GUILD_KVGG.value).members

        for member in members:
            if member.bot:
                continue

            if not (dcUserDb := getDiscordUser(member, session)):
                logger.error(f"couldn't fetch DiscordUser for {member.display_name}")

                return

            await self._createQuestForMember(member, dcUserDb, time, session)

            # if member is not online don't add progress to certain quests
            if not member.voice:
                continue

            # weil wir die online user hier sowieso schon haben: checke direkt auf streak und online
            await self.addProgressToQuest(member, QuestType.ONLINE_STREAK)
            logger.debug(f"added progress for {member.name} for online streak if applicable")
            await self.addProgressToQuest(member, QuestType.DAYS_ONLINE)
            logger.debug(f"added progress for {member.name} for days online if applicable")

    @classmethod
    def insertNewQuestsForMember(cls, member: Member, time: QuestDates, session: Session) -> bool:
        # noinspection PyTypeChecker
        getQuery = select(Quest).where(Quest.time_type == time.value)

        try:
            quests = session.scalars(getQuery).all()
        except Exception as error:
            logger.error("couldn't fetch quests from database", exc_info=error)

            return False

        usedIndices = []
        stop = False
        currentAmount = 0

        # use bool because of continues
        while not stop:
            randomNumber = random.randint(0, len(quests) - 1)

            # don't add same two quests into the list
            if randomNumber in usedIndices:
                continue

            # noinspection PyTypeChecker
            insertQuery = insert(QuestDiscordMapping).values(quest_id=quests[randomNumber].id,
                                                             time_created=datetime.now(),
                                                             discord_id=(select(DiscordUser.id)
                                                                         .where(DiscordUser.user_id == str(member.id))
                                                                         .scalar_subquery()), )

            try:
                session.execute(insertQuery)
            except Exception as error:
                logger.error(f"couldn't save quest_discord_mapping to database", exc_info=error)

                continue

            logger.debug(f"added {quests[randomNumber]} to {member.display_name} quests")
            usedIndices.append(randomNumber)

            currentAmount += 1

            if currentAmount == QuestDates.getQuestAmountForDate(time):
                stop = True

        try:
            session.commit()
        except Exception as error:
            logger.error(f"couldn't save new quests for {member.display_name}", exc_info=error)
            session.rollback()

            return False
        else:
            logger.debug(f"added {time.value} quests for {member.display_name}")

            return True

    async def _createQuestForMember(self, member: Member, dcUserDb: DiscordUser, time: QuestDates, session: Session):
        """
        Creates new quests for the given member and time.

        :param member: Member, who will get new quests.
        :param time: Type of quests
        :param session:
        """
        if not self.insertNewQuestsForMember(member, time, session):
            logger.error(f"couldn't insert new quests for {dcUserDb} and time: {time}")

            return

        await self._informMemberAboutNewQuests(member, time, session)

    def listQuests(self, member: Member) -> str:
        """
        Lists all the quests from a user.

        :param member: Member, who requested his quests
        """
        if not (session := getSession()):
            return "Es gab einen Fehler!"

        if not (quests := getQuestDiscordMapping(member, session)):
            logger.error(f"couldn't fetch quests for {member.display_name}")
            session.close()

            return "Es gab einen Fehler!"

        daily = []
        weekly = []
        monthly = []

        for quest in quests:
            if quest.quest.time_type == "daily":
                daily.append(quest)
            elif quest.quest.time_type == "weekly":
                weekly.append(quest)
            elif quest.quest.time_type == "monthly":
                monthly.append(quest)
            else:
                logger.error(f"undefined quest time found: {quest.quest.time_type}")

                continue

        def addEmoji(quest) -> str:
            if quest.current_value >= quest.quest.value_to_reach:
                return self.questAccomplished + "\n"
            else:
                return self.questNotAccomplished + "\n"

        answer = "Du hast folgende aktive Quests:\n\n__**Dailys**__:\n"

        for quest in daily:
            answer += (f"- {quest.quest.description} Aktueller Wert: **{quest.current_value}**, von: "
                       f"{quest.quest.value_to_reach} {quest.quest.unit} ")
            answer += addEmoji(quest)

        answer += "\n__**Weeklys**__:\n"

        for quest in weekly:
            answer += (f"- {quest.quest.description} Aktueller Wert: **{quest.current_value}**, von: "
                       f"{quest.quest.value_to_reach} {quest.quest.unit} ")
            answer += addEmoji(quest)

        answer += "\n__**Monthlys**__:\n"

        for quest in monthly:
            answer += (f"- {quest.quest.description} Aktueller Wert: **{quest.current_value}**, von: "
                       f"{quest.quest.value_to_reach} {quest.quest.unit} ")
            answer += addEmoji(quest)

        session.close()

        return answer
