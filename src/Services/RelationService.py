import asyncio
import logging
from datetime import datetime
from enum import Enum

from discord import ChannelType, Member, VoiceState, Client

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.Helper.GetFormattedTime import getFormattedTime
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Id.ChannelIdUniversityTracking import ChannelIdUniversityTracking
from src.Id.ChannelIdWhatsAppAndTracking import ChannelIdWhatsAppAndTracking
from src.Id.GuildId import GuildId
from src.Repository.DiscordUserRepository import getDiscordUser
from src.Services.AchievementService import AchievementService
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
        self.database = Database()
        self.client = client

    def __createRelation(self, member_1: Member, member_2: Member, type: RelationTypeEnum) -> bool:
        """
        Creates a new relation between the two given members

        :param member_1:
        :param member_2:
        :param type:
        :return:
        """
        member1 = getDiscordUser(member_1)
        member2 = getDiscordUser(member_2)

        if not member1 or not member2:
            logger.debug("couldn't create relation")

            return False
        elif member1['id'] == member2['id']:
            logger.debug("given member were the same one")

            return False

        query = "INSERT INTO discord_user_relation " \
                "(discord_user_id_1, discord_user_id_2, type, created_at) " \
                "VALUES (%s, %s, %s, %s)"

        self.database.runQueryOnDatabase(query,
                                              (member1['id'], member2['id'], type.value, datetime.now(),))

        return True

    async def getRelationBetweenUsers(self, member_1: Member, member_2: Member, type: RelationTypeEnum) -> dict | None:
        """
        Returns the relation of the given type and users

        :param member_2:
        :param member_1:
        :param type:
        :return:
        """
        if member_1.id == member_2.id:
            logger.debug("same member for relation")

            return None

        dcUserDb_1: dict | None = getDiscordUser(member_1)
        dcUserDb_2: dict | None = getDiscordUser(member_2)

        if not dcUserDb_1 or not dcUserDb_2:
            logger.warning(
                "couldn't create relation, %s has no entity" % (member_1.name if not dcUserDb_1 else member_2.name))

            return None

        query = "SELECT * " \
                "FROM discord_user_relation " \
                "WHERE type = %s AND " \
                "((discord_user_id_1 = %s AND discord_user_id_2 = %s) " \
                "OR (discord_user_id_1 = %s AND discord_user_id_2 = %s))"

        relation = self.database.fetchOneResult(query,
                                                (type.value,
                                                 dcUserDb_1['id'],
                                                 dcUserDb_2['id'],
                                                 dcUserDb_2['id'],
                                                 dcUserDb_1['id'],))

        if not relation:
            if self.__createRelation(member_1, member_2, type):
                relation = self.database.fetchOneResult(query,
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
        :return:
        """
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

            if self.database.runQueryOnDatabase(query, nones):
                logger.debug("saved increased relation to database")
            else:
                logger.critical("couldn't save relation into database")
        else:
            logger.debug("couldn't fetch relation")

    async def manageLeavingMember(self, member: Member, voiceStateBefore: VoiceState):
        """
        Sets the last parameters if one member leaves

        :param member:
        :param voiceStateBefore:
        :return:
        """
        logger.debug("managing leaving member for relation")
        await lock.acquire()
        logger.debug("lock acquired")

        try:
            otherMembersInChannel = voiceStateBefore.channel.members
            whatsappChannels: set = ChannelIdWhatsAppAndTracking.getValues()
            allTrackedChannels: set = whatsappChannels | ChannelIdUniversityTracking.getValues()

            if len(otherMembersInChannel) <= 0:
                logger.debug("last member in channel, relations were handled by their partners")

                return

            if str(voiceStateBefore.channel.id) not in allTrackedChannels:
                logger.debug("relation outside of allowed region")

                return

            if str(voiceStateBefore.channel.id) in ChannelIdWhatsAppAndTracking.getValues():
                type = RelationTypeEnum.ONLINE
            else:
                type = RelationTypeEnum.UNIVERSITY

            for otherMember in otherMembersInChannel:
                relation = await self.getRelationBetweenUsers(member, otherMember, type)

                if not relation:
                    logger.warning("couldn't fetch relation")

                    continue

                relation['last_time'] = datetime.now()
                relation['frequency'] = relation['frequency'] + 1
                query, nones = writeSaveQuery("discord_user_relation", relation['id'], relation)

                self.database.runQueryOnDatabase(query, nones)
            logger.debug("edited all relations for leave")

            if voiceStateBefore.self_video or voiceStateBefore.self_stream:
                for otherMember in otherMembersInChannel:
                    if otherMember.voice.self_stream or otherMember.voice.self_video:
                        relation = await self.getRelationBetweenUsers(member, otherMember, RelationTypeEnum.STREAM)

                        if not relation:
                            logger.warning("couldn't fetch relation")

                            continue

                        relation['last_time'] = datetime.now()
                        relation['frequency'] = relation['frequency'] + 1
                        query, nones = writeSaveQuery("discord_user_relation", relation['id'], relation)

                        self.database.runQueryOnDatabase(query, nones)

                logger.debug("edited all relations for leave")
        finally:
            logger.debug("lock will be released")
            lock.release()

    async def increaseAllRelation(self):
        """
        Increases all relations at the same time on this server

        :return:
        """
        whatsAppChannels: set = ChannelIdWhatsAppAndTracking.getValues()
        allTrackedChannels: set = ChannelIdUniversityTracking.getValues() | whatsAppChannels

        for channel in self.client.get_guild(int(GuildId.GUILD_KVGG.value)).channels:
            # skip none voice channels
            if channel.type != ChannelType.voice:
                continue

            # skip empty or less than 2 member channels
            if len(channel.members) <= 1:
                # logger.debug("channel %s empty or with less than 2" % channel.name)

                continue

            # skip none tracked channels
            if str(channel.id) not in allTrackedChannels:
                continue

            members = channel.members

            # for every member with every member
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    logger.debug("looking at %s and %s" % (members[i].name, members[j].name))

                    # depending on the channel increase correct relation
                    if str(channel.id) in whatsAppChannels:
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

        :param type: RelationTypeEnum to choose which relation to look at
        :return:
        """
        answer = ""
        query = "SELECT * " \
                "FROM discord_user_relation " \
                "WHERE type = %s AND value > 0 " \
                "ORDER BY value DESC " \
                "LIMIT %s"
        relations = self.database.fetchAllResults(query, (type.value, limit,))

        if relations:
            logger.debug("fetched top three relations from database")

            query = "SELECT username FROM discord WHERE id = %s"

            for index, relation in enumerate(relations, 1):
                dcUserDb_1 = self.database.fetchOneResult(query, (relation['discord_user_id_1'],))

                if not dcUserDb_1:
                    answer += "\t%d: Es gab hier einen Fehler!\n" % index

                    logger.debug("couldn't fetch the first DiscordUser for relation %d" % relation['id'])

                    continue

                dcUserDb_2 = self.database.fetchOneResult(query, (relation['discord_user_id_2'],))

                if not dcUserDb_2:
                    answer += "\t%d: Es gab hier einen Fehler!\n" % index

                    logger.debug("couldn't fetch the second DiscordUser for relation %d" % relation['id'])

                    continue

                answer += "\t%d: %s und %s - %s\n" % (
                    index, dcUserDb_1['username'], dcUserDb_2['username'], getFormattedTime(relation['value']))

            if answer == "":
                logger.warning("there was a problem with the DiscordUsers everytime")

                return None
            return answer
        else:
            logger.debug("couldn't fetch data from database, type: %s" % type.value)

            return None
