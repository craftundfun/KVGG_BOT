import datetime
import logging
import random

from discord import Client, Member, VoiceChannel

from src.DiscordParameters.QuestParameter import QuestDates
from src.Helper.GetChannelsFromCategory import getVoiceChannelsFromCategoryEnum
from src.Helper.SendDM import sendDM
from src.Id.Categories import TrackedCategories
from src.Id.GuildId import GuildId
from src.Repository.DiscordUserRepository import getDiscordUser
from src.Services.Database import Database

logger = logging.getLogger("KVGG_BOT")


class QuestService:

    def __init__(self, client: Client):
        self.database = Database()
        self.client = client
        self.allowedChannelsForNewQuestMessage: list[VoiceChannel] = getVoiceChannelsFromCategoryEnum(self.client,
                                                                                                      TrackedCategories)

    def resetQuests(self, time: QuestDates):
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

        self.__createQuestsForCurrentOnlineUsers(time)

    async def __informMemberAboutNewQuests(self, member: Member, time: QuestDates, channel: VoiceChannel):
        if channel not in self.allowedChannelsForNewQuestMessage:
            return

        query = ("SELECT * FROM quest "
                 "WHERE id in "
                 "(SELECT id FROM quest_discord_mapping WHERE discord_id = "
                 "(SELECT id FROM discord WHERE user_id = %s))")

        if not (quests := self.database.fetchAllResults(query, (member.id,))):
            logger.error(f"couldn't fetch quests to message {member.nick if member.nick else member.name}")

            return

        message = f"Es gibt neue {time.value}-Quests: \n\n"

        for quest in quests:
            message += f"- {quest['description']}\n"

        await sendDM(member, message)
        # TODO in NotificationService auslagern

    def __createQuestsForCurrentOnlineUsers(self, time: QuestDates):
        for channel in self.__getChannels():
            for member in channel.members:
                print("found member")
                print(member)
                self.__createQuestForMember(member, time)
                self.__informMemberAboutNewQuests(member, time, channel)

    def checkQuestsForJoinedMember(self, member: Member):
        dcUserDb = getDiscordUser(member)

        if not dcUserDb:
            logger.warning(f"couldn't fetch DiscordUser for {member.nick if member.nick else member.name}")

            return

        now = datetime.datetime.now()
        last_online: datetime.datetime | None = dcUserDb['last_online']

        # member has not been online yet or year has changed -> create all quests
        if not last_online or now.year > last_online.year:
            self.__createQuestForMember(member, QuestDates.DAILY)
            self.__createQuestForMember(member, QuestDates.WEEKLY)
            self.__createQuestForMember(member, QuestDates.MONTHLY)

            # TODO message user
            return

        # user will get new monthly's -> don't care to reset, already done through the background service
        if now.month > last_online.month:
            self.__createQuestForMember(member, QuestDates.MONTHLY)

        # user will get new weekly's -> don't care to reset, already done through the background service
        if now.isocalendar()[1] > last_online.isocalendar()[1]:
            self.__createQuestForMember(member, QuestDates.WEEKLY)

        if now.day > last_online.day or now.month > last_online.month or now.year > last_online.year:
            self.__createQuestForMember(member, QuestDates.DAILY)

        # TODO
        if member.voice.channel in self.allowedChannelsForNewQuestMessage:
            pass

    def __createQuestForMember(self, member: Member, time: QuestDates):
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
                                                     datetime.datetime.now())):
                logger.error("couldn't save quest_discord_mapping to database")

                continue

            usedIndices.append(randomNumber)
            currentAmount += 1

            if currentAmount == QuestDates.getQuestAmountForDate(time):
                stop = True

    def __getChannels(self):
        """
        Yields all channels to track from the guild filtered by number of members and if they are tracked

        :return:
        """
        for channel in self.client.get_guild(GuildId.GUILD_KVGG.value).voice_channels:
            if len(channel.members) > 0:
                yield channel

    def listQuests(self, member: Member) -> str:
        # TODO list progress
        query = ("SELECT * "
                 "FROM quest "
                 "WHERE id IN "
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
            answer += f"- {quest['description']}\n"

        answer += "\n__**Weeklys**__:\n"

        for quest in weekly:
            answer += f"- {quest['description']}\n"

        answer += "\n__**Monthlys**__:\n"

        for quest in monthly:
            answer += f"- {quest['description']}\n"

        return answer
