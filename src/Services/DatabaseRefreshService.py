from __future__ import annotations

import logging

from datetime import datetime
from discord import Client, ChannelType
from src.Helper import WriteSaveQuery
from src.Helper.CreateNewDatabaseConnection import getDatabaseConnection
from src.Id.GuildId import GuildId
from src.Repository.DiscordUserRepository import getDiscordUser

logger = logging.getLogger("KVGG_BOT")


class DatabaseRefreshService:

    def __init__(self, client: Client):
        self.databaseConnection = getDatabaseConnection()
        self.client = client

    async def startUp(self):
        """
        Brings the database up to the current state of the server

        :param client: Discord client
        :return:
        """
        logger.debug("Beginning fetching data")

        with self.databaseConnection.cursor() as cursor:
            query = "SELECT * FROM discord"

            cursor.execute(query)

            data = cursor.fetchall()

            if not data:
                logger.critical("found not entries in discord database")
                return

            dcUsersDb = [dict(zip(cursor.column_names, date)) for date in data]

        logger.debug("compare database against discord")

        # for every user from the database
        for user in dcUsersDb:
            foundInChannel = False

            # look in every channel
            for channel in self.client.get_all_channels():
                if foundInChannel:
                    break

                # filter out none voice channels
                if channel.type != ChannelType.voice:
                    continue

                members = channel.members

                # for every member in this voice channel
                for member in members:
                    # if the user was found, save the (new) channel id and break
                    if member.id == int(user['user_id']):
                        user['channel_id'] = channel.id
                        user['joined_at'] = datetime.now()
                        voiceState = channel.voice_states[member.id]

                        if voiceState.self_mute:
                            user['muted_at'] = datetime.now()
                        else:
                            user['muted_at'] = None

                        if voiceState.self_deaf:
                            user['full_muted_at'] = datetime.now()
                        else:
                            user['full_muted_at'] = None

                        if voiceState.self_stream:
                            user['started_stream_at'] = datetime.now()
                        else:
                            user['started_stream_at'] = None

                        if voiceState.self_video:
                            user['started_webcam_at'] = datetime.now()
                        else:
                            user['started_webcam_at'] = None

                        foundInChannel = True
                        break

            if not foundInChannel:
                # overwrite last online only if user was previously in a channel
                if user['channel_id']:
                    user['last_online'] = datetime.now()
                user['channel_id'] = None
                user['joined_at'] = None
                user['started_stream_at'] = None
                user['started_webcam_at'] = None
                user['muted_at'] = None
                user['full_muted_at'] = None

            # update nick
            if (member := self.client.get_guild(int(GuildId.GUILD_KVGG.value)).get_member(int(user['user_id']))):
                user['username'] = member.nick if member.nick else member.name

        with self.databaseConnection.cursor() as cursor:
            for user in dcUsersDb:
                query, nones = WriteSaveQuery.writeSaveQuery(
                    'discord',
                    user['id'],
                    user,
                )

                cursor.execute(query, nones)

        self.databaseConnection.commit()

        # check for new members that aren't in our database
        for channel in self.client.get_all_channels():
            if channel.type != ChannelType.voice:
                continue

            for member in channel.members:
                dcUserDb = getDiscordUser(self.databaseConnection, member)

                if dcUserDb is None:
                    logger.error("Couldnt create new entry for %s!" % member.name)

        self.databaseConnection.commit()

    async def updateDatabaseToServerState(self):
        """
        Updates the database to the current state of the discord
        (The database -> discord direction only updates member who still have channel ids,
        only these entry are cleaned up. All other entries will not be cleaned due to performance reasons, and
        it's not necessary to do so. The Cronjobs only look at online members.)

        :return:
        """
        # save online members for database -> discord comparison
        onlineMembers = {}

        # discord -> database
        for channel in self.client.get_all_channels():
            # ignore non voice channels
            if channel.type != ChannelType.voice:
                continue

            with self.databaseConnection.cursor() as cursor:
                query = "SELECT * FROM discord WHERE user_id = %s"

                # check every member per channel
                for member in channel.members:
                    onlineMembers[str(member.id)] = member
                    cursor.execute(query, (member.id,))

                    if not (data := cursor.fetchone()):
                        continue

                    dcUserDb = dict(zip(cursor.column_names, data))
                    voiceState = channel.voice_states[member.id]

                    # can change, has no side effect
                    dcUserDb['channel_id'] = channel.id
                    dcUserDb['username'] = member.nick if member.nick else member.name

                    if not dcUserDb['joined_at']:
                        dcUserDb['joined_at'] = datetime.now()

                    if voiceState.self_stream and not dcUserDb['started_stream_at']:
                        dcUserDb['started_stream_at'] = datetime.now()
                    elif not voiceState.self_stream and dcUserDb['started_stream_at']:
                        dcUserDb['started_stream_at'] = None

                    if voiceState.self_video and not dcUserDb['started_webcam_at']:
                        dcUserDb['started_webcam_at'] = datetime.now()
                    elif not voiceState.self_video and dcUserDb['started_webcam_at']:
                        dcUserDb['started_webcam_at'] = None

                    if (voiceState.self_mute or voiceState.mute) and not dcUserDb['muted_at']:
                        dcUserDb['muted_at'] = datetime.now()
                    elif not voiceState.self_mute and dcUserDb['muted_at']:
                        dcUserDb['muted_at'] = None

                    if (voiceState.self_deaf or voiceState.deaf) and not dcUserDb['full_muted_at']:
                        dcUserDb['full_muted_at'] = datetime.now()
                    elif not voiceState.self_deaf and dcUserDb['full_muted_at']:
                        dcUserDb['full_muted_at'] = None

                    saveQuery, nones = WriteSaveQuery.writeSaveQuery(
                        'discord',
                        dcUserDb['id'],
                        dcUserDb,
                    )

                    cursor.execute(saveQuery, nones)

                self.databaseConnection.commit()

        with self.databaseConnection.cursor() as cursor:
            # only look for still online members c.f. doc
            query = "SELECT * FROM discord WHERE channel_id IS NOT NULL"

            cursor.execute(query)

            if not (data := cursor.fetchall()):
                return

            dcUsersDb = [dict(zip(cursor.column_names, date)) for date in data]

            for dcUserDb in dcUsersDb:
                # if a member gets returned, we know that he / she was served already
                if str(dcUserDb['user_id']) in onlineMembers:
                    continue

                dcUserDb['last_online'] = datetime.now()
                dcUserDb['channel_id'] = None
                dcUserDb['joined_at'] = None
                dcUserDb['started_stream_at'] = None
                dcUserDb['started_webcam_at'] = None
                dcUserDb['muted_at'] = None
                dcUserDb['full_muted_at'] = None

                saveQuery, nones = WriteSaveQuery.writeSaveQuery(
                    'discord',
                    dcUserDb['id'],
                    dcUserDb,
                )

                cursor.execute(saveQuery, nones)

            self.databaseConnection.commit()

    async def updateAllMembers(self):
        """
        Updates all members in the database. Profile picture, nickname etc.

        :return:
        """
        with self.databaseConnection.cursor() as cursor:
            query = "SELECT * FROM discord"

            cursor.execute(query)

            if not (data := cursor.fetchall()):
                logger.warning("Couldn't fetch members from database!")
                
                return

            dcUsersDb = [dict(zip(cursor.column_names, date)) for date in data]
            logger.debug("Fetched %s members from database" % len(dcUsersDb))

            for dcUserDb in dcUsersDb:
                member = self.client.get_guild(int(GuildId.GUILD_KVGG.value)).get_member(int(dcUserDb['user_id']))

                if not member:
                    continue

                dcUserDb['username'] = member.nick if member.nick else member.name
                dcUserDb['profile_picture_discord'] = member.display_avatar

                query, nones = WriteSaveQuery.writeSaveQuery('discord', dcUserDb['id'], dcUserDb)

                cursor.execute(query, nones)
                logger.debug("Updated %s" % dcUserDb['username'])

            self.databaseConnection.commit()
            logger.debug("Uploaded changes to database")

    def __del__(self):
        self.databaseConnection.close()
