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

        :param member: Member who joined the hub and the channel will be named after
        :param voiceStateAfter: State of the member after joining a voice channel
        :return:
        """
        async with lock:
            if not (category := self.__getCategory()):
                logger.critical("couldn't fetch category -> couldn't create new channel")

                return

            if not voiceStateAfter.channel:
                logger.debug("channel was None")

                return

            # filter out non hub channels
            if not voiceStateAfter.channel.id == self.HUB_ID:
                logger.debug("not hub-channel")

                return

            if len(self.client.get_channel(self.HUB_ID).members) == 0:
                logger.debug("aborting creation of new channel, no users left to move")

                return

            # +1 to ignore hub, -1 because hub has no number = +/-0
            name = "Gaming - %s" % member.name

            if not (voiceChannel := await self.__createNewChannel(name, len(category.voice_channels), category)):
                logger.critical("couldn't create new channel")

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

                # users were moved / left beforehand
                if moved == 0:
                    await voiceChannel.delete(reason="no users left to join - empty")

    async def __createNewChannel(self, name: str, position: int, category: CategoryChannel) -> VoiceChannel | None:
        if category is None:
            logger.critical("couldn't create voice channel, category is None")

            return None

        try:
            voiceChannel = await category.create_voice_channel(name, position=position)
        except Exception as error:
            logger.error("couldn't create voice channel", exc_info=error)

            return None
        else:
            return voiceChannel

    async def memberSwitchedVoiceChannel(self,
                                         member: Member,
                                         voiceStateBefore: VoiceState,
                                         voiceStateAfter: VoiceState):
        channelBefore = voiceStateBefore.channel
        channelAfter = voiceStateAfter.channel
        category = self.__getCategory()

        async with lock:
            # member switched within category
            if channelBefore.category.id == self.CATEGORY and channelAfter.category.id == self.CATEGORY:
                # if left channel is empty delete it
                if len(channelBefore.members) == 0 and channelBefore.id != self.HUB_ID:
                    await channelBefore.delete(reason="no one uses this channel anymore")

                # switched to hub
                if channelAfter.id == self.HUB_ID:
                    voiceChannel = await self.__createNewChannel("Gaming - %s" % member.name,
                                                                 len(category.voice_channels),
                                                                 category)

                    if not voiceChannel:
                        logger.critical("couldn't create voice channel")

                        return

                    try:
                        await member.move_to(voiceChannel)
                    except Exception as error:
                        logger.error("couldn't move %s to new channel" % member.name, exc_info=error)

                        return

                    return
            # member left category
            else:
                if len(channelBefore.members) == 0 and channelBefore.id != self.HUB_ID:
                    await channelBefore.delete(reason="no one uses this channel anymore")

    async def memberLeftVoiceChannel(self, voiceStateBefore: VoiceState):
        async with lock:
            if voiceStateBefore.channel not in self.__getCategory().voice_channels:
                logger.debug("channel was not in tracked hub category")

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
