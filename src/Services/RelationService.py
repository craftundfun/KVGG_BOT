import logging
from datetime import datetime
from enum import Enum

import discord
from discord import ChannelType

from src.Helper.CreateNewDatabaseConnection import getDatabaseConnection
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Id.ChannelIdUniversityTracking import ChannelIdUniversityTracking
from src.Id.ChannelIdWhatsAppAndTracking import ChannelIdWhatsAppAndTracking
from src.Id.GuildId import GuildId
from src.Repository.DiscordUserRepository import getDiscordUserById

logger = logging.getLogger("KVGG_BOT")


class RelationTypeEnum(Enum):
    ONLINE = "online"
    STREAM = "stream"
    UNIVERSITY = "university"
    MESSAGE = "message"


class RelationService:

    def __init__(self, client: discord.Client):
        self.databaseConnection = getDatabaseConnection()
        self.client = client

    async def getRelationBetweenUsers(self, userId_1: int, userId_2: int, type: RelationTypeEnum) -> dict | None:
        """
        Returns the relation of the given type and users

        :param userId_1:
        :param userId_2:
        :param type:
        :return:
        """
        dcUserDb_1 = getDiscordUserById(self.databaseConnection, userId_1)
        dcUserDb_2 = getDiscordUserById(self.databaseConnection, userId_2)

        if not dcUserDb_1 or not dcUserDb_2:
            logger.warning("couldnt create relation, %d has no entity" % (userId_1 if not dcUserDb_1 else userId_2))

            return None

        with self.databaseConnection.cursor() as cursor:
            query = "SELECT * " \
                    "FROM relation " \
                    "WHERE type = %s AND " \
                    "((discord_user_id_1 = %s AND discord_user_id_2 = %s) " \
                    "OR (discord_user_id_1 = %s AND discord_user_id_2 = %s))"

            cursor.execute(query, (type.value, dcUserDb_1['id'], dcUserDb_2['id'], dcUserDb_2['id'], dcUserDb_1['id'],))

            if not (data := cursor.fetchone()):
                return None
            else:
                return dict(zip(cursor.column_names, data))

    async def increaseRelation(self, userId_1: int, userId_2: int, type: RelationTypeEnum, value: int = 1):
        """
        Raises a relation of a specific couple. It creates a new relation if possible and if there is none.

        :param userId_1: ID of first user
        :param userId_2: ID of second user
        :param type: Type of the relation
        :param value: Value to be increased
        :return:
        """
        if not (relation := await self.getRelationBetweenUsers(userId_1, userId_2, type)):
            dcUserDb_1 = getDiscordUserById(self.databaseConnection, userId_1)
            dcUserDb_2 = getDiscordUserById(self.databaseConnection, userId_2)

            if not dcUserDb_1 or not dcUserDb_2:
                logger.warning("couldnt create relation, %d has no entity" % (userId_1 if not dcUserDb_1 else userId_2))

                return

            with self.databaseConnection.cursor() as cursor:
                query = "INSERT INTO relation " \
                        "(discord_user_id_1, discord_user_id_2, type, created_at, value, last_time) " \
                        "VALUES ((SELECT id FROM discord WHERE user_id = %s), " \
                        "(SELECT id FROM discord WHERE user_id = %s), %s, %s, %s, %s)"

                cursor.execute(query, (userId_1, userId_2, type.value, datetime.now(), value, datetime.now(),))
                self.databaseConnection.commit()

                if not await self.getRelationBetweenUsers(userId_1, userId_2, type):
                    logger.warning("couldnt create relation between %s and %s" % (
                        dcUserDb_1['username'], dcUserDb_2['username']))
        else:
            relation['value'] = relation['value'] + value

            with self.databaseConnection.cursor() as cursor:
                query, nones = writeSaveQuery("relation", relation['id'], relation)

                cursor.execute(query, nones)
                self.databaseConnection.commit()
                logger.debug("saved increased relation to database")

    async def setLastTime(self, userId_1: int, userId_2: int, *types: RelationTypeEnum):
        """
        Changes the last_time of all given types of relations to now and increases the frequency counter by 1.

        :param userId_1: ID of first user
        :param userId_2: ID of second user
        :param types: List of relation types
        :return:
        """
        with self.databaseConnection.cursor() as cursor:
            for type in types:
                relation = await self.getRelationBetweenUsers(userId_1, userId_2, type)

                if not relation:
                    logger.debug("relation %s between %d and %d skipped" % (type.value, userId_1, userId_2))

                    continue

                relation['last_time'] = datetime.now()
                relation['frequency'] = relation['frequency'] + 1

                query, nones = writeSaveQuery('relation', relation['id'], relation)

                cursor.execute(query, nones)
                logger.debug("set relation of type %s in queue" % type.value)

            self.databaseConnection.commit()
            logger.debug("saved relations into database")

    async def increaseAllRelation(self):
        """
        Increases all relations at the same time on this server

        :return:
        """
        lookedPairs = []

        for channel in self.client.get_guild(int(GuildId.GUILD_KVGG.value)).channels:
            # skip none voice channels
            if channel.type != ChannelType.voice:
                continue

            # skip none tracked channels
            if str(channel.id) not in ChannelIdWhatsAppAndTracking.getValues() or \
                    str(channel.id) not in ChannelIdUniversityTracking.getValues():
                continue

            # skip empty or less than 2 member channels
            if len(channel.members) <= 1:
                logger.debug("channel %s empty or with less than 2" % channel.name)

                continue

            members = channel.members

            # for every member with every member
            for member_1 in members:
                for member_2 in members:
                    # skip the same member
                    if member_1 == member_2:
                        continue

                    # create tuple for later comparison
                    couple = (member_1.id, member_2.id)

                    # when a couple already existed, skip it
                    if sorted(couple) in lookedPairs:
                        logger.debug("skipping %s and %s" % couple)

                        continue

                    logger.debug("looking at %s and %s" % couple)

                    # append the couple to list
                    lookedPairs.append(sorted(couple))

                    # depending on the channel increase correct relation
                    if str(channel.id) in ChannelIdWhatsAppAndTracking.getValues():
                        await self.increaseRelation(member_1.id, member_2.id, RelationTypeEnum.ONLINE)
                    else:
                        await self.increaseRelation(member_1.id, member_2.id, RelationTypeEnum.UNIVERSITY)

                    # increase streaming relation if both are streaming at the same time
                    if (member_1.voice.self_stream or member_1.voice.self_video) and \
                            (member_2.voice.self_stream or member_2.voice.self_video):
                        await self.increaseRelation(member_1.id, member_2.id, RelationTypeEnum.STREAM)

            # clear looked pairs for next channel
            lookedPairs = []
