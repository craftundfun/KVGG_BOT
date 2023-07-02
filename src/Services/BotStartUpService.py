import logging
import os
from datetime import datetime

import discord
from discord import Client, ChannelType
from src.Helper import WriteSaveQuery
from src.Helper.createNewDatabaseConnection import getDatabaseConnection
from src.Id.ChannelId import ChannelId
from src.Id.GuildId import GuildId
from src.Repository.DiscordUserRepository import getDiscordUser

logger = logging.getLogger("KVGG_BOT")


class BotStartUpService:

    def __init__(self):
        self.databaseConnection = getDatabaseConnection()

    async def startUp(self, client: Client):
        """
        Brings the database up to the current state of the server

        :param client: Discord client
        :return:
        """
        logger.info("Beginning fetching data")

        with self.databaseConnection.cursor() as cursor:
            query = "SELECT * FROM discord"

            cursor.execute(query)

            data = cursor.fetchall()

            if not data:
                return

            dcUsersDb = [dict(zip(cursor.column_names, date)) for date in data]

        # for every user from the database
        for user in dcUsersDb:
            foundInChannel = False
            # look in every channel
            for channel in client.get_all_channels():
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
            if (member := client.get_guild(int(GuildId.GUILD_KVGG.value)).get_member(int(user['user_id']))):
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
        for channel in client.get_all_channels():
            if channel.type != ChannelType.voice:
                continue

            for member in channel.members:
                dcUserDb = getDiscordUser(self.databaseConnection, member)

                if dcUserDb is None:
                    logger.error("Couldnt create new entry for %s!" % member.name)

        self.databaseConnection.commit()

        #if os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False):
        #    await client.get_channel(int(ChannelId.CHANNEL_BOT_TEST_ENVIRONMENT.value)).send(
        #        file=discord.File("./Logs/log.txt"))

    def __del__(self):
        self.databaseConnection.close()
