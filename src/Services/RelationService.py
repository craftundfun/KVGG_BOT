import asyncio
import logging
from datetime import datetime
from enum import Enum

from discord import ChannelType, Member, VoiceState, Client

from src.Helper.CreateNewDatabaseConnection import getDatabaseConnection
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Id.ChannelIdUniversityTracking import ChannelIdUniversityTracking
from src.Id.ChannelIdWhatsAppAndTracking import ChannelIdWhatsAppAndTracking
from src.Id.GuildId import GuildId
from src.Repository.DiscordUserRepository import getDiscordUser
from src.Helper.GetFormattedTime import getFormattedTime

logger = logging.getLogger("KVGG_BOT")


class RelationTypeEnum(Enum):
    ONLINE = "online"
    STREAM = "stream"
    UNIVERSITY = "university"


# static lock
lock = asyncio.Lock()


class RelationService:

    def __init__(self, client: Client):
        self.databaseConnection = getDatabaseConnection()
        self.client = client

    def __createRelation(self, member_1: Member, member_2: Member, type: RelationTypeEnum) -> bool:
        """
        Creates a new relation between the two given members

        :param member_1:
        :param member_2:
        :param type:
        :return:
        """
        member1 = getDiscordUser(self.databaseConnection, member_1)
        member2 = getDiscordUser(self.databaseConnection, member_2)

        if not member1 or not member2:
            logger.debug("couldn't create relation")

            return False
        elif member1['id'] == member2['id']:
            logger.debug("given member were the same one")

            return False

        with self.databaseConnection.cursor() as cursor:
            query = "INSERT INTO discord_user_relation " \
                    "(discord_user_id_1, discord_user_id_2, type, created_at) " \
                    "VALUES (%s, %s, %s, %s)"

            cursor.execute(query, (member1['id'], member2['id'], type.value, datetime.now(),))
            self.databaseConnection.commit()

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

        dcUserDb_1: dict | None = getDiscordUser(self.databaseConnection, member_1)
        dcUserDb_2 = getDiscordUser(self.databaseConnection, member_2)

        if not dcUserDb_1 or not dcUserDb_2:
            logger.warning(
                "couldn't create relation, %s has no entity" % (member_1.name if not dcUserDb_1 else member_2.name))

            return None

        with self.databaseConnection.cursor() as cursor:
            query = "SELECT * " \
                    "FROM discord_user_relation " \
                    "WHERE type = %s AND " \
                    "((discord_user_id_1 = %s AND discord_user_id_2 = %s) " \
                    "OR (discord_user_id_1 = %s AND discord_user_id_2 = %s))"

            cursor.execute(query, (type.value, dcUserDb_1['id'], dcUserDb_2['id'], dcUserDb_2['id'], dcUserDb_1['id'],))

            if not (data := cursor.fetchone()):
                if self.__createRelation(member_1, member_2, type):
                    cursor.execute(query, (
                        type.value, dcUserDb_1['id'], dcUserDb_2['id'], dcUserDb_2['id'], dcUserDb_1['id'],))

                    if not (data := cursor.fetchone()):
                        logger.warning("couldn't fetch relation for %s and %s" % (member_1.name, member_2.name))

                        return None
                    return dict(zip(cursor.column_names, data))
                else:
                    logger.warning("couldn't fetch relation for %s and %s" % (member_1.name, member_2.name))

                    return None
            else:
                return dict(zip(cursor.column_names, data))

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

            with self.databaseConnection.cursor() as cursor:
                query, nones = writeSaveQuery("discord_user_relation", relation['id'], relation)

                cursor.execute(query, nones)
                self.databaseConnection.commit()
                logger.debug("saved increased relation to database")
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

            with self.databaseConnection.cursor() as cursor:
                for otherMember in otherMembersInChannel:
                    relation = await self.getRelationBetweenUsers(member, otherMember, type)

                    if not relation:
                        logger.warning("couldn't fetch relation")

                        continue

                    relation['last_time'] = datetime.now()
                    relation['frequency'] = relation['frequency'] + 1
                    query, nones = writeSaveQuery("discord_user_relation", relation['id'], relation)

                    cursor.execute(query, nones)

                logger.debug("edited all relations for leave")
                self.databaseConnection.commit()

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

                            cursor.execute(query, nones)

                    logger.debug("edited all relations for leave")
                    self.databaseConnection.commit()
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
                logger.debug("channel %s empty or with less than 2" % channel.name)

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

        with self.databaseConnection.cursor() as cursor:
            query = "SELECT * " \
                    "FROM discord_user_relation " \
                    "WHERE type = %s AND value > 0 " \
                    "ORDER BY value DESC " \
                    "LIMIT %s"

            cursor.execute(query, (type.value, limit, ))

            data = cursor.fetchall()

            if data:
                relations = [dict(zip(cursor.column_names, date)) for date in data]

                logger.debug("fetched top three relations from database")
                cursor.reset()

                query = "SELECT username FROM discord WHERE id = %s"

                for index, relation in enumerate(relations, 1):
                    cursor.execute(query, (relation['discord_user_id_1'],))

                    if not (dcUserDb_1 := cursor.fetchone()):
                        answer += "\t%d: Es gab hier einen Fehler!\n" % index

                        logger.debug("couldn't fetch the first DiscordUser for relation %d" % relation['id'])

                        continue

                    dcUserDb_1 = dict(zip(cursor.column_names, dcUserDb_1))

                    cursor.reset()
                    cursor.execute(query, (relation['discord_user_id_2'],))

                    if not (dcUserDb_2 := cursor.fetchone()):
                        answer += "\t%d: Es gab hier einen Fehler!\n" % index

                        logger.debug("couldn't fetch the second DiscordUser for relation %d" % relation['id'])

                        continue

                    dcUserDb_2 = dict(zip(cursor.column_names, dcUserDb_2))

                    answer += "\t%d: %s und %s - %s\n" % (
                        index, dcUserDb_1['username'], dcUserDb_2['username'], getFormattedTime(relation['value']))

                if answer == "":
                    logger.warning("there was a problem with the DiscordUsers everytime")

                    return None
                return answer
            else:
                logger.debug("couldn't fetch data from database, type: %s" % type.value)

                return None
