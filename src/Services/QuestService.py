import logging
import random

from discord import Client, Member, VoiceChannel

from src.DiscordParameters.QuestParameter import QuestDates
from src.Helper.GetChannelsFromCategory import getVoiceChannelsFromCategoryEnum
from src.Helper.SendDM import sendDM
from src.Id.Categories import TrackedCategories
from src.Id.GuildId import GuildId
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
                "WHERE id = " \
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

    def __createQuestsForCurrentOnlineUsers(self, time: QuestDates):
        for channel in self.__getChannels():
            for member in channel.members:
                self.createQuestForMember(member, time)
                self.__informMemberAboutNewQuests(member, time, channel)

    def createQuestForMember(self, member: Member, time: QuestDates):
        query = "SELECT * FROM quest WHERE time_type = %s"

        if not (quests := self.database.fetchAllResults(query, (time.value,))):
            logger.error(f"couldn't fetch any quests from the database and the given time: {time.value}")

            return

        usedIndices = []
        stop = False
        query = "INSERT INTO quest_discord_mapping (quest_id, discord_id) " \
                "VALUES (%s, (SELECT id FROM discord WHERE user_id = %s))"
        currentAmount = 0

        # use bool because of continues
        while not stop:
            randomNumber = random.randint(0, len(quests) - 1)

            # don't add same two quests into the list
            if randomNumber in usedIndices:
                continue

            if not self.database.runQueryOnDatabase(query, (quests[randomNumber]['id'], member.id,)):
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
        for channel in self.client.get_guild(GuildId.GUILD_KVGG.value).channels:
            if len(channel.members) > 0:
                yield channel
