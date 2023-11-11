import logging
import random
from datetime import datetime
from enum import Enum

from discord import Client, Member, VoiceChannel

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.DiscordParameters.QuestParameter import QuestDates
from src.Helper.DictionaryFuntionKeyDecorator import validateKeys
from src.Helper.GetChannelsFromCategory import getVoiceChannelsFromCategoryEnum
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Id.Categories import TrackedCategories
from src.Id.GuildId import GuildId
from src.Repository.DiscordUserRepository import getDiscordUser
from src.Services.Database import Database
from src.Services.ExperienceService import ExperienceService
from src.Services.NotificationService import NotificationService

logger = logging.getLogger("KVGG_BOT")


class QuestType(Enum):
    MESSAGE_COUNT = "message_count"
    COMMAND_COUNT = "command_count"
    ONLINE_TIME = "online_time"
    STREAM_TIME = "stream_time"
    DAYS_ONLINE = "days_online"
    ONLINE_STREAK = "online_streak"


class QuestService:

    def __init__(self, client: Client):
        self.database = Database()
        self.client = client
        self.allowedChannelsForNewQuestMessage: list[VoiceChannel] = getVoiceChannelsFromCategoryEnum(self.client,
                                                                                                      TrackedCategories)
        self.notificationService = NotificationService(self.client)
        self.experienceService = ExperienceService(self.client)

    async def addProgressToQuest(self, member: Member, questType: QuestType, value: int = 1):
        """
        Based on the type of quest, the member will earn progress for this quest.

        :param member: Member, whose quests will be checked
        :param questType: Type of quest
        :param value: Optional value to overwrite the standard increase of one
        """
        query = ("SELECT qdm.*, q.value_to_reach, q.time_type "
                 "FROM quest_discord_mapping qdm INNER JOIN quest q ON quest_id = q.id "
                 "WHERE quest_id IN "
                 "(SELECT id FROM quest WHERE type = %s) "
                 "AND discord_id = "
                 "(SELECT id FROM discord WHERE user_id = %s)")

        if not (quests := self.database.fetchAllResults(query, (questType.value, member.id,))):
            logger.debug(f"no quests found to type {questType.value} and {member.name}")

            return

        for quest in quests:
            lastUpdated: datetime | None = quest['time_updated']

            # special checks for special quests
            if questType == QuestType.DAYS_ONLINE:
                # if its same day the count cant be increased
                if lastUpdated and lastUpdated.day == datetime.now().day:
                    continue

            elif questType == QuestType.ONLINE_STREAK:
                # if its same day the count cant be increased
                if lastUpdated and datetime.now().day == lastUpdated.day:
                    continue

                # if the difference is too big, the progress will be lost
                if lastUpdated and datetime.now().day - lastUpdated.day > 1:
                    # reset value due to loss in streak
                    quest['current_value'] = 0
                    quest['time_updated'] = None

                    query, nones = writeSaveQuery("quest_discord_mapping", quest['id'], quest)

                    if not self.database.runQueryOnDatabase(query, nones):
                        logger.error(f"couldn't save changes to database for {member.name}, query: {query}")

                    continue

            quest['current_value'] += value
            quest['time_updated'] = datetime.now()

            await self.__checkForFinishedQuest(member, quest)

            # remove value_to_reach key due it's online for comparison and doesn't belong into quest_discord_mapping
            del quest['value_to_reach']
            del quest['time_type']

            query, nones = writeSaveQuery("quest_discord_mapping", quest['id'], quest)

            if not self.database.runQueryOnDatabase(query, nones):
                logger.error(f"couldn't save changes to database for {member.name}, query: {query}")

    async def __checkForFinishedQuest(self, member: Member, quest: dict):
        """
        If a quest was finished a xp-boost will be given to the user.

        :param member: Member, who completed the quest and will get the boost
        :param quest: Dictionary of the quest in the database with current_value from the mapping
        """
        if quest['current_value'] == quest['value_to_reach']:
            await self.notificationService.sendQuestFinishNotification(member, quest['quest_id'])

            if quest['time_type'] == "daily":
                boost = AchievementParameter.DAILY_QUEST
            elif quest['time_type'] == "weekly":
                boost = AchievementParameter.WEEKLY_QUEST
            else:
                boost = AchievementParameter.MONTHLY_QUEST

            self.experienceService.grantXpBoost(member, boost)

    async def resetQuests(self, time: QuestDates):
        """
        Resets all the quest from the given time and creates new ones for members who are currently online.

        :param time: Time to reset the quests and create new ones
        """
        query = "DELETE FROM quest_discord_mapping " \
                "WHERE quest_id IN " \
                "(SELECT id FROM quest WHERE time_type = %s)"

        if not self.database.runQueryOnDatabase(query, (time.value,)):
            logger.error("failure to run query on database")

            return

        await self.__createQuestsForCurrentOnlineUsers(time)

    async def __informMemberAboutNewQuests(self, member: Member, time: QuestDates):
        """
        Fetches all current quests from the given time and informs user about them.

        :param member: Member to message
        :param time: Type of quests
        """
        query = ("SELECT * FROM quest "
                 "WHERE id IN "
                 "(SELECT quest_id FROM quest_discord_mapping WHERE discord_id = "
                 "(SELECT id FROM discord WHERE user_id = %s)) AND time_type = %s")

        if not (quests := self.database.fetchAllResults(query, (member.id, time.value,))):
            logger.error(f"couldn't fetch quests to message {member.nick if member.nick else member.name}")

            return

        await self.notificationService.informAboutNewQuests(member, time, quests)

    async def __createQuestsForCurrentOnlineUsers(self, time: QuestDates):
        """
        Creates new quests for all online users, so they have new ones right at zero 'o clock.

        :param time: Type of quests
        """
        for channel in self.__getChannels():
            for member in channel.members:
                await self.__createQuestForMember(member, time)

    async def checkQuestsForJoinedMember(self, member: Member):
        """
        If a member joins the VoiceChat, this function will check if the member receives new quests and gives
        them to them.

        :param member: Member, who joined the VoiceChat
        """
        dcUserDb = getDiscordUser(member)

        if not dcUserDb:
            logger.warning(f"couldn't fetch DiscordUser for {member.nick if member.nick else member.name}")

            return

        now = datetime.now()
        last_online: datetime | None = dcUserDb['last_online']

        query = "SELECT id FROM quest_discord_mapping WHERE discord_id = (SELECT id FROM discord WHERE user_id = %s)"

        if not (currentQuests := self.database.fetchAllResults(query, (member.id,))):
            length = 0
        else:
            length = len(currentQuests)

        # member has not been online yet or year has changed -> create all quests
        if not last_online or now.year > last_online.year or length == 0:
            logger.debug("no quests yet or quests too old, generate new ones for every time")

            await self.__createQuestForMember(member, QuestDates.DAILY)
            await self.__createQuestForMember(member, QuestDates.WEEKLY)
            await self.__createQuestForMember(member, QuestDates.MONTHLY)

            return

        # user will get new monthly's -> don't care to reset, already done through the background service
        if now.month > last_online.month:
            logger.debug("create new monthly quests")

            await self.__createQuestForMember(member, QuestDates.MONTHLY)

        # user will get new weekly's -> don't care to reset, already done through the background service
        if now.isocalendar()[1] > last_online.isocalendar()[1]:
            logger.debug("create new weekly quests")

            await self.__createQuestForMember(member, QuestDates.WEEKLY)

        if now.day > last_online.day or now.month > last_online.month or now.year > last_online.year:
            logger.debug("create new daily quests")

            await self.__createQuestForMember(member, QuestDates.DAILY)

    async def __createQuestForMember(self, member: Member, time: QuestDates):
        """
        Creates new quests for the given member and time.

        :param member: Member, who will get new quests.
        :param time: Type of quests
        """
        query = "SELECT * FROM quest WHERE time_type = %s"

        if not (quests := self.database.fetchAllResults(query, (time.value,))):
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

            if not self.database.runQueryOnDatabase(query,
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

        await self.__informMemberAboutNewQuests(member, time)

    def __getChannels(self):
        """
        Yields all channels to track from the guild filtered by number of members and if they are tracked

        :return: Generator for VoiceChannels with more than zero users
        """
        for channel in self.client.get_guild(GuildId.GUILD_KVGG.value).voice_channels:
            if len(channel.members) > 0:
                yield channel

    @validateKeys
    def listQuests(self, member: Member) -> str:
        """
        Lists all the quests from a user.

        :param member: Member, who requested his quests
        """
        query = ("SELECT q.*, qdm.current_value "
                 "FROM quest q INNER JOIN quest_discord_mapping qdm ON q.id = qdm.quest_id "
                 "WHERE q.id IN "
                 "(SELECT quest_id FROM quest_discord_mapping WHERE discord_id = "
                 "(SELECT id FROM discord WHERE user_id = %s))")

        if not (quests := self.database.fetchAllResults(query, (member.id,))):
            logger.warning(f"couldn't fetch results for following query: {query}")

            return "Es gab ein Problem beim Abfragen der Quests oder du hast keine Quests!"

        # to give the sort function the key to sort from
        def sort_key(dictionary):
            return dictionary["time_type"]

        # first 3 daily, next 3 monthly, next 3 weekly
        quests = sorted(quests, key=sort_key)
        daily = quests[:3]
        weekly = quests[6:]
        monthly = quests[3:6]
        answer = "Du hast folgende aktive Quests:\n\n__**Dailys**__:\n"

        for quest in daily:
            answer += (f"- {quest['description']} Aktueller Wert: **{quest['current_value']}**, von: "
                       f"{quest['value_to_reach']}\n")

        answer += "\n__**Weeklys**__:\n"

        for quest in weekly:
            answer += (f"- {quest['description']} Aktueller Wert: **{quest['current_value']}**, von: "
                       f"{quest['value_to_reach']}\n")

        answer += "\n__**Monthlys**__:\n"

        for quest in monthly:
            answer += (f"- {quest['description']} Aktueller Wert: **{quest['current_value']}**, von: "
                       f"{quest['value_to_reach']}\n")

        return answer
