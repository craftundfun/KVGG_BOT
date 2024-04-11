import asyncio
import logging
from enum import Enum

from discord import ChannelType, Member, Client, VoiceChannel
from sqlalchemy.orm import Session

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.Helper.GetChannelsFromCategory import getVoiceChannelsFromCategoryEnum
from src.Helper.GetFormattedTime import getFormattedTime
from src.Id.Categories import TrackedCategories, UniversityCategory
from src.Id.GuildId import GuildId
from src.Manager.AchievementManager import AchievementService
from src.Manager.DatabaseManager import getSession
from src.Repository.UserRelation.Repository.DiscordUserRelationRepository import getRelationBetweenUsers
from src.Services.Database_Old import Database_Old

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

        self.achievementService = AchievementService(self.client)

    async def increaseRelation(self,
                               member_1: Member,
                               member_2: Member,
                               type: RelationTypeEnum,
                               session: Session,
                               value: int = 1):
        """
        Raises a relation of a specific couple. It creates a new relation if possible and if there is none.

        :param member_2:
        :param member_1:
        :param type: Type of the relation
        :param value: Value to be increased
        :param session:
        :return:
        """
        if relation := getRelationBetweenUsers(member_1, member_2, type, session):
            relation.value += value

            # check for grant-able achievements
            match type:
                case RelationTypeEnum.ONLINE:
                    if (relation.value % (AchievementParameter.RELATION_ONLINE_TIME_HOURS.value * 60)) == 0:
                        await self.achievementService.sendAchievementAndGrantBoostForRelation(
                            member_1,
                            member_2,
                            AchievementParameter.RELATION_ONLINE,
                            relation.value,
                        )
                case RelationTypeEnum.STREAM:
                    if (relation.value % (AchievementParameter.RELATION_STREAM_TIME_HOURS.value * 60)) == 0:
                        await self.achievementService.sendAchievementAndGrantBoostForRelation(
                            member_1,
                            member_2,
                            AchievementParameter.RELATION_STREAM,
                            relation.value,
                        )
                case RelationTypeEnum.UNIVERSITY:
                    pass
                case _:
                    logger.error(f"undefined enum-entry was reached: {type}")

            try:
                session.commit()
            except Exception as error:
                logger.error(f"couldn't save DiscordUserRelation for {member_1.display_name} and "
                             f"{member_2.display_name}",
                             exc_info=error, )
        else:
            logger.error(f"couldn't fetch DiscordUserRelation for {member_1.display_name} and "
                         f"{member_2.display_name}")

    async def increaseAllRelations(self):
        """
        Increases all relations at the same time on this server

        :return:
        """
        whatsappChannels: list[VoiceChannel] = getVoiceChannelsFromCategoryEnum(self.client, TrackedCategories)
        universityChannels: list[VoiceChannel] = getVoiceChannelsFromCategoryEnum(self.client, UniversityCategory)
        allTrackedChannels: list[VoiceChannel] = whatsappChannels + universityChannels

        if not (session := getSession()):  # TODO outside
            return

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
                    logger.debug(f"looking at {members[i].display_name} and {members[j].display_name}")

                    # depending on the channel increase correct relation
                    relation_type = RelationTypeEnum.ONLINE if channel in whatsappChannels \
                        else RelationTypeEnum.UNIVERSITY
                    await self.increaseRelation(members[i], members[j], relation_type, session)

                    # increase streaming relation if both are streaming at the same time
                    if (members[i].voice.self_stream or members[i].voice.self_video) and \
                            (members[j].voice.self_stream or members[j].voice.self_video):
                        await self.increaseRelation(members[i], members[j], RelationTypeEnum.STREAM, session)

    async def getLeaderboardFromType(self, type: RelationTypeEnum, limit: int = 3) -> str | None:
        """
        Returns the top 3 relations from the given type

        :param limit:
        :param type: RelationTypeEnum to choose which relation to look at
        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        database = Database_Old()

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
