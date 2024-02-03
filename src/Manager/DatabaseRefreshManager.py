from __future__ import annotations

import logging
from datetime import datetime

from discord import Client, ChannelType

from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Id.GuildId import GuildId
from src.Repository.DiscordUserRepository import getDiscordUser
from src.Services.Database import Database

logger = logging.getLogger("KVGG_BOT")


class DatabaseRefreshService:

    def __init__(self, client: Client):
        """
        :param client:
        :raise ConnectionError:
        """
        self.client = client

    async def startUp(self):
        """
        Brings the database up to the current state of the server

        :return:
        """
        logger.debug("beginning fetching data")

        database = Database()
        query = "SELECT * FROM discord"
        dcUsersDb = database.fetchAllResults(query)

        if dcUsersDb is None:
            return

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
            if member := self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(int(user['user_id'])):
                user['username'] = member.nick if member.nick else member.name

            query, nones = writeSaveQuery(
                'discord',
                user['id'],
                user,
            )
            if not database.runQueryOnDatabase(query, nones):
                logger.critical("couldn't save changes to database")

        # check for new members that aren't in our database
        for channel in self.client.get_all_channels():
            if channel.type != ChannelType.voice:
                continue

            for member in channel.members:
                dcUserDb = getDiscordUser(member, database)

                if dcUserDb is None:
                    logger.error("couldn't create new entry for %s!" % member.name)

    async def updateAllMembers(self):
        """
        Updates all members in the database. Profile picture, nickname etc.

        :return:
        """
        database = Database()
        query = "SELECT * FROM discord"
        dcUsersDb = database.fetchAllResults(query)

        if not dcUsersDb:
            logger.error("couldn't fetch any discord users")

            return

        logger.debug("fetched %s members from database" % len(dcUsersDb))

        for dcUserDb in dcUsersDb:
            member = self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(int(dcUserDb['user_id']))

            if not member:
                continue

            dcUserDb['username'] = member.nick if member.nick else member.name
            dcUserDb['profile_picture_discord'] = member.display_avatar
            dcUserDb['channel_id'] = member.voice.channel.id if member.voice else None

            query, nones = writeSaveQuery('discord', dcUserDb['id'], dcUserDb)

            if database.runQueryOnDatabase(query, nones):
                logger.debug("updated %s" % dcUserDb['username'])
            else:
                logger.error("couldn't save changes to database")

        logger.debug("uploaded changes to database")
