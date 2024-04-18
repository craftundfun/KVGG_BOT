from __future__ import annotations

import logging
from datetime import datetime

from discord import Client, ChannelType
from sqlalchemy import select, null

from src.Id.GuildId import GuildId
from src.Manager.DatabaseManager import getSession
from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser

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

        if not (session := getSession()):
            return

        getQuery = select(DiscordUser)

        try:
            dcUsersDb = session.scalars(getQuery).all()
        except Exception as error:
            logger.error("couldn't fetch DiscordUsers", exc_info=error)
            session.close()

            return

        if not dcUsersDb:
            logger.error("no DiscordUsers")

            return

        logger.debug("comparing database against discord")

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
                    if member.id == int(user.user_id):
                        user.channel_id = channel.id
                        user.joined_at = datetime.now()
                        voiceState = channel.voice_states[member.id]

                        if voiceState.self_mute:
                            user.muted_at = datetime.now()
                        else:
                            user.muted_at = null()

                        if voiceState.self_deaf:
                            user.full_muted_at = datetime.now()
                        else:
                            user.full_muted_at = null()

                        if voiceState.self_stream:
                            user.started_stream_at = datetime.now()
                        else:
                            user.started_stream_at = null()

                        if voiceState.self_video:
                            user.started_webcam_at = datetime.now()
                        else:
                            user.started_webcam_at = null()

                        foundInChannel = True
                        break

            if not foundInChannel:
                # overwrite last online only if user was previously in a channel
                if user.channel_id:
                    user.last_online = datetime.now()

                user.channel_id = null()
                user.joined_at = null()
                user.started_stream_at = null()
                user.started_webcam_at = null()
                user.muted_at = null()
                user.full_muted_at = null()

            # update nick
            if member := self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(int(user.user_id)):
                user.username = member.display_name
                user.discord_name = member.name

            try:
                session.commit()
            except Exception as error:
                logger.error(f"couldn't commit {user}", exc_info=error)
                session.rollback()
            else:
                logger.debug(f"updated {user}")

        session.close()
