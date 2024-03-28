import asyncio
import logging
import random
from datetime import datetime
from enum import Enum

from discord import Client, Member
from sqlalchemy import select, null

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.DiscordParameters.QuestParameter import QuestDates
from src.Id.Categories import TrackedCategories
from src.Id.GuildId import GuildId
from src.Manager.DatabaseManager import getSession
from src.Manager.NotificationManager import NotificationService
from src.Repository.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Repository.DiscordUserRepository import getDiscordUserOld
from src.Repository.Quest.Entity.Quest import Quest
from src.Repository.Quest.Entity.QuestDiscordMapping import QuestDiscordMapping
from src.Services.Database_Old import Database_Old
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

    async def addProgressToQuest(self, member: Member, questType: QuestType, value: int = 1):
        """
        Based on the type of quest, the member will earn progress for this quest.

        :param member: Member, whose quests will be checked
        :param questType: Type of quest
        :param value: Optional value to overwrite the standard increase of one
        :raise ConnectionError: If the database connection cant be established
        """
        if not (session := getSession()):
            return

        getQuery = (select(QuestDiscordMapping)
                    .where(QuestDiscordMapping.quest_id.in_(select(Quest.id)
                                                            .where(Quest.type == questType.value)
                                                            .scalar_subquery()),
                           QuestDiscordMapping.discord_id == (select(DiscordUser.id)
                                                              .where(DiscordUser.user_id == str(member.id))
                                                              .scalar_subquery()),))

        # use lock here to avoid giving spammers more boosts
        async with lock:
            try:
                quests = session.scalars(getQuery).all()
            except Exception as error:
                logger.error("failure to fetch quests from database", exc_info=error)
                session.close()

                return

            for quest in quests:
                # print(quest)
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

    async def _checkForFinishedQuest(self, member: Member, qdm: QuestDiscordMapping):
        """
        If a quest was finished a xp-boost will be given to the user.

        :param member: Member, who completed the quest and will get the boost
        :param qdm: QuestDiscordMapping
        """
        if qdm.current_value == qdm.quest.value_to_reach:
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
        :raise ConnectionError: If the database connection cant be established
        """
        database = Database_Old()

        query = "DELETE FROM quest_discord_mapping " \
                "WHERE quest_id IN " \
                "(SELECT id FROM quest WHERE time_type = %s)"

        if not database.runQueryOnDatabase(query, (time.value,)):
            logger.error("failure to run query on database")

            return
        else:
            logger.debug(f"resettet {time.value}-quests")

        await self._createQuestsForAllUsers(time, database)

    async def _informMemberAboutNewQuests(self, member: Member, time: QuestDates, database: Database_Old):
        """
        Fetches all current quests from the given time and informs user about them.

        :param member: Member to message
        :param time: Type of quests
        :param database:
        """
        # if the member is not online
        if not member.voice:
            return

        query = ("SELECT * FROM quest "
                 "WHERE id IN "
                 "(SELECT quest_id FROM quest_discord_mapping WHERE discord_id = "
                 "(SELECT id FROM discord WHERE user_id = %s)) AND time_type = %s")

        if not (quests := database.fetchAllResults(query, (member.id, time.value,))):
            logger.error(f"couldn't fetch quests to message {member.nick if member.nick else member.name}")

            return

        await self.notificationService.informAboutNewQuests(member, time, quests)

    async def _createQuestsForAllUsers(self, time: QuestDates, database: Database_Old):
        """
        Creates new quests for all online users, so they have new ones right at zero 'o clock.

        :param time: Type of quests
        """
        members = self.client.get_guild(GuildId.GUILD_KVGG.value).members
        query = "SELECT user_id FROM discord"

        if not (ids := database.fetchAllResults(query)):
            logger.error("couldn't fetch all ids from discord database")

            return

        memberIds = []

        for id in ids:
            memberIds.append(int(id['user_id']))

        for member in members:
            if member.bot:
                continue

            if member.id not in memberIds:
                logger.warning(f"{member.display_name} not in database, continuing")

                continue

            await self._createQuestForMember(member, time, database)

            # if member is not online don't add progress to certain quests
            if not member.voice:
                continue

            # weil wir die online user hier sowieso schon haben: checke direkt auf streak und online
            await self.addProgressToQuest(member, QuestType.ONLINE_STREAK)
            logger.debug(f"added progress for {member.name} for online streak")
            await self.addProgressToQuest(member, QuestType.DAYS_ONLINE)
            logger.debug(f"added progress for {member.name} for days online")

    async def checkQuestsForJoinedMember(self, member: Member):
        """
        If a member joins the VoiceChat, this function will check if the member receives new quests and gives
        them to them.

        :param member: Member, who joined the VoiceChat
        :raise ConnectionError: If the database connection cant be established
        """
        database = Database_Old()
        dcUserDb = getDiscordUserOld(member, database)

        if not dcUserDb:
            logger.warning(f"couldn't fetch DiscordUser for {member.display_name}")

            return

        last_online: datetime | None = dcUserDb['last_online']

        query = "SELECT id FROM quest_discord_mapping WHERE discord_id = (SELECT id FROM discord WHERE user_id = %s)"

        if not (currentQuests := database.fetchAllResults(query, (member.id,))):
            length = 0
        else:
            length = len(currentQuests)

        # member has not been online yet -> create all quests
        if not last_online or length == 0:
            logger.debug("no quests yet or quests too old, generate new ones for every time")

            await self._createQuestForMember(member, QuestDates.DAILY, database)
            await self._createQuestForMember(member, QuestDates.WEEKLY, database)
            await self._createQuestForMember(member, QuestDates.MONTHLY, database)

            return

    async def createQuestsForNewMember(self, member: Member):
        """
        Creates all quest typs for the newly joined member.
        """
        database: Database_Old = Database_Old()

        await self._createQuestForMember(member, QuestDates.DAILY, database)
        await self._createQuestForMember(member, QuestDates.WEEKLY, database)
        await self._createQuestForMember(member, QuestDates.MONTHLY, database)

    async def _createQuestForMember(self, member: Member, time: QuestDates, database: Database_Old):
        """
        Creates new quests for the given member and time.

        :param member: Member, who will get new quests.
        :param time: Type of quests
        :param database:
        """
        query = "SELECT * FROM quest WHERE time_type = %s"

        if not (quests := database.fetchAllResults(query, (time.value,))):
            logger.error(f"couldn't fetch any quests from the database and the given time: {time.value}")

            return

        usedIndices = []
        stop = False
        query = "INSERT INTO quest_discord_mapping (quest_id, discord_id, time_created) " \
                "VALUES (%s, (SELECT id FROM discord WHERE user_id = %s), %s)"
        currentAmount = 0

        # use bool because of continues
        while not stop:
            randomNumber = random.randint(0, len(quests) - 1)

            # don't add same two quests into the list
            if randomNumber in usedIndices:
                continue

            if not database.runQueryOnDatabase(query,
                                               (quests[randomNumber]['id'],
                                                member.id,
                                                datetime.now())):
                logger.error("couldn't save quest_discord_mapping to database")

                break

            logger.debug(f"added {quests[randomNumber]} to {member.name} quests")
            usedIndices.append(randomNumber)

            currentAmount += 1

            if currentAmount == QuestDates.getQuestAmountForDate(time):
                stop = True

        logger.debug("added all quests")

        await self._informMemberAboutNewQuests(member, time, database)

    def listQuests(self, member: Member) -> str:
        """
        Lists all the quests from a user.

        :param member: Member, who requested his quests
        :raise ConnectionError: If the database connection cant be established
        """
        if not (session := getSession()):
            return "Es gab einen Fehler!"

        getQuery = (select(QuestDiscordMapping)
                    .where(QuestDiscordMapping.discord_id == (select(DiscordUser.id)
                                                              .where(DiscordUser.user_id == str(member.id))
                                                              .scalar_subquery())))

        try:
            quests = session.scalars(getQuery).all()
        except Exception as error:
            logger.error(f"couldn't fetch quests for {member.display_name}", exc_info=error)
            session.close()

            return "Es gab einen Fehler!"

        if not quests:
            logger.warning(f"{member.display_name} has no active quests")
            session.close()

            return "Du hast aktuell keine Quests!"

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

    async def remindToFulFillQuests(self, questDate: QuestDates):
        """
        Reminds all currently online users about eventual unfinished quests.

        :param questDate: The date of the quest to remind
        """
        database = Database_Old()

        def _getChannels():
            for voiceChannel in self.client.get_guild(GuildId.GUILD_KVGG.value).voice_channels:
                if voiceChannel.category.id in TrackedCategories.getValues():
                    yield voiceChannel

        for channel in _getChannels():
            for member in channel.members:
                query = ("SELECT qdm.current_value, q.value_to_reach, q.description, q.unit "
                         "FROM quest_discord_mapping AS qdm INNER JOIN quest AS q ON q.id = qdm.quest_id "
                         "WHERE q.time_type = %s AND qdm.current_value < q.value_to_reach "
                         "AND qdm.discord_id = ("
                         "SELECT id "
                         "FROM discord AS d "
                         "WHERE d.user_id = %s"
                         ")")

                if not (unfinishedQuests := database.fetchAllResults(query, (questDate.value, member.id,))):
                    logger.debug(f"no unfinished quests for {member.display_name}")

                    continue
                else:
                    await self.notificationService.notifyAboutUnfinishedQuests(questDate, unfinishedQuests, member)
