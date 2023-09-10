import asyncio
import logging

from discord import Member, VoiceState, Client, CategoryChannel

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

    async def memberJoinedOrSwitchedToAVoiceChat(self, member: Member, voiceState: VoiceState):
        """
        Checks if the newly joined member joined into Hub. If so, he / she will be moved into a newly created channel.

        :param member: Member, who joined a voice channel
        :param voiceState: State of the member after joining a voice channel
        :return:
        """
        async with lock:
            logger.debug("lock acquired")

            if not (category := self.__getCategory()):
                logger.critical("couldn't fetch category -> couldn't create new channel")

                return

            # filter out non hub channels
            if not voiceState.channel.id == self.HUB_ID:
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

            try:
                voiceChannel = await category.create_voice_channel(name)
            except Exception as error:
                logger.error("encountered error while creating voice channel", exc_info=error)
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

    async def memberLeftVoiceChannel(self, member: Member, voiceStateBefore: VoiceState):
        if voiceStateBefore.channel not in self.__getCategory().voice_channels:
            logger.debug("channel was not in tracked category (not university tho)")

            return

        if len(voiceStateBefore.channel.members) > 0:
            return
        else:
            try:
                await voiceStateBefore.channel.delete(reason="no more users in this channel")
            except Exception as error:
                logger.error("couldn't delete channel", exc_info=error)

                return
