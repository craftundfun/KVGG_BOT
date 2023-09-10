import asyncio
import logging

from discord import Member, VoiceState, Client, CategoryChannel, VoiceChannel

from src.Id.CategoryId import CategoryWhatsappAndTrackingId
from src.Id.GuildId import GuildId
from src.Services.Database import Database

logger = logging.getLogger("KVGG_BOT")
# static lock
lock = asyncio.Lock()


class ChannelService:
    HUB_ID: int = 1150440682746548266
    CATEGORY: int = CategoryWhatsappAndTrackingId.SERVERVERWALTUNG.value  # TODO change to Gaming
    WAIT_FOR_PLAYERS_CHANNEL_NAME = "warte auf Mitspieler/innen"

    def __init__(self, client: Client):
        """
        :raise ConnectionError:
        """
        self.database = Database()
        self.client = client

    def __getCategory(self) -> CategoryChannel | None:
        """
        Returns the category for the hub to create a voice channel in.

        :return:
        """
        categories = self.client.get_guild(GuildId.GUILD_KVGG.value).categories

        for category in categories:
            if category.id == self.CATEGORY:
                return category

        return None

    async def memberJoinedAVoiceChat(self, member: Member, voiceStateAfter: VoiceState):
        """
        Checks if the newly joined member joined into Hub. If so, he / she will be moved into a newly created channel.

        :param member: Member, who joined a voice channel
        :param voiceStateAfter: State of the member after joining a voice channel
        :return:
        """
        async with lock:
            logger.debug("lock acquired")

            if not (category := self.__getCategory()):
                logger.critical("couldn't fetch category -> couldn't create new channel")

                return

            if not voiceStateAfter.channel:
                logger.debug("channel was None")

                return

            # filter out non hub channels
            if not voiceStateAfter.channel.id == self.HUB_ID:
                logger.debug("not hub-channel")

                # hub and wait for players
                if len(category.voice_channels) == 3:  # TODO change to 2
                    for channel in category.voice_channels:
                        if channel.name == self.WAIT_FOR_PLAYERS_CHANNEL_NAME:
                            try:
                                await channel.edit(name="Gaming #%d" % (len(category.voice_channels) - 1))
                            except Exception as error:
                                logger.error("couldn't change name of channel", exc_info=error)
                            else:
                                logger.debug("renamed channel to Gaming #%d" % (len(category.voice_channels) - 1))
                return

            if len(self.client.get_channel(self.HUB_ID).members) == 0:
                logger.debug("aborting creation of new channel, no users left to move")

                return

            # +1 to ignore hub, -1 because hub has no number = +/-0
            if len(category.voice_channels) == 2:  # TODO change to 1 due to Gaming category
                name = self.WAIT_FOR_PLAYERS_CHANNEL_NAME
            else:
                name = "Gaming #%d" % len(category.voice_channels)

            if not (voiceChannel := await self.__createNewChannel(name)):
                logger.critical("couldnt create new channel")

                return
            else:
                moved = 0

                for member in self.client.get_channel(self.HUB_ID).members:
                    try:
                        await member.move_to(voiceChannel)

                        moved = moved + 1
                    except Exception as error:
                        logger.error("couldn't move %s to newly created channel" % member.name, exc_info=error)

                        continue

                if moved == 0:
                    await voiceChannel.delete(reason="no users left to join - empty")

        logger.debug("lock released")

    async def __createNewChannel(self, name: str) -> VoiceChannel | None:
        category = self.__getCategory()

        if category is None:
            logger.critical("couldn't create voice channel, category is None")

            return None

        try:
            voiceChannel = await category.create_voice_channel(name)
        except Exception as error:
            logger.error("couldnt create voice channel", exc_info=error)

            return None
        else:
            return voiceChannel

    async def memberSwitchedVoiceChannel(self,
                                         member: Member,
                                         voiceStateBefore: VoiceState,
                                         voiceStateAfter: VoiceState):
        channelBefore = voiceStateBefore.channel
        channelAfter = voiceStateAfter.channel

        async with lock:
            # member switched from outside the category
            if channelBefore.category.id != self.CATEGORY and channelAfter.category.id == self.CATEGORY:
                # joined voicechannel still has waiting name => change it
                if channelAfter.name == self.WAIT_FOR_PLAYERS_CHANNEL_NAME and len(channelAfter.members) >= 2:
                    await channelAfter.edit(name="Gaming #%d" % (len(self.__getCategory().voice_channels)))
            # member switched within category
            elif channelBefore.category.id == self.CATEGORY and channelAfter.category.id == self.CATEGORY:
                # switched to hub
                if channelAfter.id == self.HUB_ID:
                    if len(channelBefore.members) == 0:
                        await channelBefore.delete(reason="no one uses this channel anymore")

                    # if only the hub exists name the channel waiting for players
                    if len((category := self.__getCategory()).voice_channels) == 2:  # TODO change to 1
                        voiceChannel = await self.__createNewChannel(self.WAIT_FOR_PLAYERS_CHANNEL_NAME)
                    # else name the channel after the given scheme
                    else:
                        voiceChannel = await self.__createNewChannel("Gaming #%d" % (len(category.voice_channels) + 1))

                    if not voiceChannel:
                        logger.critical("couldn't create voice channel")

                        return

                    try:
                        await member.move_to(voiceChannel)
                    except Exception as error:
                        logger.error("couldn't move %s to new channel" % member.name, exc_info=error)

                        return

                    return

                # left channel is now empty => delete
                if len(channelBefore.members) == 0 and channelBefore.id != self.HUB_ID:
                    await channelBefore.delete(reason="no one uses this channel anymore")

                # joined voicechannel still has waiting name => change it
                if channelAfter.name == self.WAIT_FOR_PLAYERS_CHANNEL_NAME and len(channelAfter.members) >= 2:
                    await channelAfter.edit(name="Gaming #%d" % (len(self.__getCategory().voice_channels)))
            # member left category
            else:
                if len(channelBefore.members) == 0:
                    await channelBefore.delete(reason="no one uses this channel anymore")

    async def memberLeftVoiceChannel(self, member: Member, voiceStateBefore: VoiceState):
        async with lock:
            if voiceStateBefore.channel not in self.__getCategory().voice_channels:
                logger.debug("channel was not in tracked category (not university tho)")

                return
            # never risk to delete hub
            elif voiceStateBefore.channel.id == self.HUB_ID:
                return

            if len(voiceStateBefore.channel.members) > 0:
                return
            else:
                try:
                    await voiceStateBefore.channel.delete(reason="no more users in this channel")
                except Exception as error:
                    logger.error("couldn't delete channel", exc_info=error)

                    return
