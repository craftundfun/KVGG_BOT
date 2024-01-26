import asyncio
import logging
from datetime import datetime
from enum import Enum

from discord import ChannelType, Member, Client, VoiceChannel

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.Helper.GetChannelsFromCategory import getVoiceChannelsFromCategoryEnum
from src.Helper.GetFormattedTime import getFormattedTime
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Id.Categories import TrackedCategories, UniversityCategory
from src.Id.GuildId import GuildId
from src.Manager.AchievementManager import AchievementService
from src.Repository.DiscordUserRepository import getDiscordUser
from src.Services.Database import Database

logger = logging.getLogger("KVGG_BOT")


class RelationTypeEnum(Enum):
    ONLINE = "online"
    STREAM = "stream"
    UNIVERSITY = "university"


# static lock
lock = asyncio.Lock()


class RelationService:

    def __init__(self, client: Client):
        """
        :param client:
        :raise ConnectionError:
        """
        self.client = client

    def _createRelation(self, member_1: Member, member_2: Member, type: RelationTypeEnum, database: Database) -> bool:
        """
        Creates a new relation between the two given members

        :param member_1:
        :param member_2:
        :param type:
        :param database:
        :return:
        """
        member1 = getDiscordUser(member_1, database)
        member2 = getDiscordUser(member_2, database)

        if not member1 or not member2:
            logger.debug("couldn't create relation")

            return False
        elif member1['id'] == member2['id']:
            logger.debug("given member were the same one")

            return False

        query = "INSERT INTO discord_user_relation " \
                "(discord_user_id_1, discord_user_id_2, type, created_at) " \
                "VALUES (%s, %s, %s, %s)"

        database.runQueryOnDatabase(query, (member1['id'], member2['id'], type.value, datetime.now(),))

        return True

    async def getRelationBetweenUsers(self, member_1: Member, member_2: Member, type: RelationTypeEnum) -> dict | None:
        """
        Returns the relation of the given type and users

        :param member_2:
        :param member_1:
        :param type:
        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        database = Database()

        if member_1.id == member_2.id:
            logger.debug("same member for relation")

            return None

        if member_1.bot or member_2.bot:
            logger.debug("one of the users were a bot")

            return None

        dcUserDb_1: dict | None = getDiscordUser(member_1, database)
        dcUserDb_2: dict | None = getDiscordUser(member_2, database)

        if not dcUserDb_1 or not dcUserDb_2:
            logger.warning("couldn't create relation, %s has no entity"
                           % (member_1.name if not dcUserDb_1 else member_2.name))

            return None

        query = "SELECT * " \
                "FROM discord_user_relation " \
                "WHERE type = %s AND " \
                "((discord_user_id_1 = %s AND discord_user_id_2 = %s) " \
                "OR (discord_user_id_1 = %s AND discord_user_id_2 = %s))"

        relation = database.fetchOneResult(query,
                                           (type.value,
                                            dcUserDb_1['id'],
                                            dcUserDb_2['id'],
                                            dcUserDb_2['id'],
                                            dcUserDb_1['id'],))

        if not relation:
            if self._createRelation(member_1, member_2, type, database):
                relation = database.fetchOneResult(query,
                                                   (type.value,
                                                    dcUserDb_1['id'],
                                                    dcUserDb_2['id'],
                                                    dcUserDb_2['id'],
                                                    dcUserDb_1['id'],))

                if not relation:
                    logger.warning("couldn't fetch relation for %s and %s" % (member_1.name, member_2.name))

                    return None

        return relation

    async def increaseRelation(self, member_1: Member, member_2: Member, type: RelationTypeEnum, value: int = 1):
        """
        Raises a relation of a specific couple. It creates a new relation if possible and if there is none.

        :param member_2:
        :param member_1:
        :param type: Type of the relation
        :param value: Value to be increased
        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        database = Database()

        if relation := await self.getRelationBetweenUsers(member_1, member_2, type):
            relation['value'] = relation['value'] + value

            # check for grant-able achievements
            match type:
                case RelationTypeEnum.ONLINE:
                    if (relation['value'] % (AchievementParameter.RELATION_ONLINE_TIME_HOURS.value * 60)) == 0:
                        await AchievementService(self.client).sendAchievementAndGrantBoostForRelation(
                            member_1,
                            member_2,
                            AchievementParameter.RELATION_ONLINE,
                            relation['value']
                        )
                case RelationTypeEnum.STREAM:
                    if (relation['value'] % (AchievementParameter.RELATION_STREAM_TIME_HOURS.value * 60)) == 0:
                        await AchievementService(self.client).sendAchievementAndGrantBoostForRelation(
                            member_1,
                            member_2,
                            AchievementParameter.RELATON_STREAM,
                            relation['value']
                        )

            query, nones = writeSaveQuery("discord_user_relation", relation['id'], relation)

            if database.runQueryOnDatabase(query, nones):
                logger.debug("saved increased relation to database")
            else:
                logger.critical("couldn't save relation into database")
        else:
            logger.debug("couldn't fetch relation")

    async def increaseAllRelation(self):
        """
        Increases all relations at the same time on this server

        :return:
        """
        whatsappChannels: list[VoiceChannel] = getVoiceChannelsFromCategoryEnum(self.client, TrackedCategories)
        universityChannels: list[VoiceChannel] = getVoiceChannelsFromCategoryEnum(self.client, UniversityCategory)
        allTrackedChannels: list[VoiceChannel] = whatsappChannels + universityChannels

        for channel in self.client.get_guild(GuildId.GUILD_KVGG.value).channels:
            # skip none voice channels
            if channel.type != ChannelType.voice:
                continue

            # skip empty or less than 2 member channels
            if len(channel.members) <= 1:
                # logger.debug("channel %s empty or with less than 2" % channel.name)

                continue

            # skip none tracked channels
            if channel not in allTrackedChannels:
                continue

            members = channel.members

            # for every member with every member
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    logger.debug("looking at %s and %s" % (members[i].name, members[j].name))

                    # depending on the channel increase correct relation
                    if channel in whatsappChannels:
                        await self.increaseRelation(members[i], members[j], RelationTypeEnum.ONLINE)
                    else:
                        await self.increaseRelation(members[i], members[j], RelationTypeEnum.UNIVERSITY)

                    # increase streaming relation if both are streaming at the same time
                    if (members[i].voice.self_stream or members[i].voice.self_video) and \
                            (members[j].voice.self_stream or members[j].voice.self_video):
                        await self.increaseRelation(members[i], members[j], RelationTypeEnum.STREAM)

    async def getLeaderboardFromType(self, type: RelationTypeEnum, limit: int = 3) -> str | None:
        """
        Returns the top 3 relations from the given type

        :param limit:
        :param type: RelationTypeEnum to choose which relation to look at
        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        database = Database()

        answer = ""
        query = "SELECT * " \
                "FROM discord_user_relation " \
                "WHERE type = %s AND value > 0 " \
                "ORDER BY value DESC " \
                "LIMIT %s"
        relations = database.fetchAllResults(query, (type.value, limit,))

        if relations:
            logger.debug("fetched top three relations from database")

            query = "SELECT username FROM discord WHERE id = %s"

            for index, relation in enumerate(relations, 1):
                dcUserDb_1 = database.fetchOneResult(query, (relation['discord_user_id_1'],))

                if not dcUserDb_1:
                    answer += "\t%d: Es gab hier einen Fehler!\n" % index

                    logger.debug("couldn't fetch the first DiscordUser for relation %d" % relation['id'])

                    continue

                dcUserDb_2 = database.fetchOneResult(query, (relation['discord_user_id_2'],))

                if not dcUserDb_2:
                    answer += "\t%d: Es gab hier einen Fehler!\n" % index

                    logger.debug("couldn't fetch the second DiscordUser for relation %d" % relation['id'])

                    continue

                answer += "\t%d: %s und %s - %s Stunden\n" % (
                    index, dcUserDb_1['username'], dcUserDb_2['username'], getFormattedTime(relation['value']))

            if answer == "":
                logger.warning("there was a problem with the DiscordUsers everytime")

                return None
            return answer
        else:
            logger.debug("couldn't fetch data from database, type: %s" % type.value)

            return None
