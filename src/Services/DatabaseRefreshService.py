from __future__ import annotations

import logging
from datetime import datetime

from discord import Client, ChannelType

from src.Helper import WriteSaveQuery
from src.Services.Database import Database
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Id.GuildId import GuildId
from src.Repository.DiscordUserRepository import getDiscordUser

logger = logging.getLogger("KVGG_BOT")


class DatabaseRefreshService:

    def __init__(self, client: Client):
        """
        :param client:
        :raise ConnectionError:
        """
        self.database = Database()
        self.client = client

    async def startUp(self):
        """
        Brings the database up to the current state of the server

        :return:
        """
        logger.debug("beginning fetching data")

        query = "SELECT * FROM discord"
        dcUsersDb = self.database.queryAllResults(query)

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
            if member := self.client.get_guild(int(GuildId.GUILD_KVGG.value)).get_member(int(user['user_id'])):
                user['username'] = member.nick if member.nick else member.name

            query, nones = writeSaveQuery(
                'discord',
                user['id'],
                user,
            )
            if not self.database.saveChangesToDatabase(query, nones):
                logger.critical("couldn't save changes to database")

        # check for new members that aren't in our database
        for channel in self.client.get_all_channels():
            if channel.type != ChannelType.voice:
                continue

            for member in channel.members:
                dcUserDb = getDiscordUser(member)

                if dcUserDb is None:
                    logger.error("couldn't create new entry for %s!" % member.name)

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

            query = "SELECT * FROM discord WHERE user_id = %s"

            # check every member per channel
            for member in channel.members:
                onlineMembers[str(member.id)] = member

                if not (dcUserDb := self.database.queryOneResult(query, (member.id,))):
                    continue

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

                saveQuery, nones = writeSaveQuery(
                    'discord',
                    dcUserDb['id'],
                    dcUserDb,
                )

                if not self.database.saveChangesToDatabase(saveQuery, nones):
                    logger.critical("couldn't save changes to database")

        # only look for still online members c.f. doc
        query = "SELECT * FROM discord WHERE channel_id IS NOT NULL"

        dcUsersDb = self.database.queryAllResults(query)

        if not dcUsersDb:
            return

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

            saveQuery, nones = writeSaveQuery(
                'discord',
                dcUserDb['id'],
                dcUserDb,
            )

            if not self.database.saveChangesToDatabase(saveQuery, nones):
                logger.critical("couldn't save changes to database")

    async def updateAllMembers(self):
        """
        Updates all members in the database. Profile picture, nickname etc.

        :return:
        """
        query = "SELECT * FROM discord"

        dcUsersDb = self.database.queryAllResults(query)

        if not dcUsersDb:
            return

        logger.debug("fetched %s members from database" % len(dcUsersDb))

        for dcUserDb in dcUsersDb:
            member = self.client.get_guild(int(GuildId.GUILD_KVGG.value)).get_member(int(dcUserDb['user_id']))

            if not member:
                continue

            dcUserDb['username'] = member.nick if member.nick else member.name
            dcUserDb['profile_picture_discord'] = member.display_avatar

            query, nones = WriteSaveQuery.writeSaveQuery('discord', dcUserDb['id'], dcUserDb)

            if self.database.saveChangesToDatabase(query, nones):
                logger.debug("updated %s" % dcUserDb['username'])
            else:
                logger.critical("couldn't save changes to database")

        logger.debug("Uploaded changes to database")
