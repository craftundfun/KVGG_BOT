import asyncio
import logging

import discord.errors
from discord import Client, Member, VoiceChannel, CategoryChannel, VoiceState

from src.Helper.MoveMembesToVoicechannel import moveMembers
from src.Id.Categories import TrackedCategories
from src.Id.ChannelId import ChannelId
from src.Id.DiscordUserId import DiscordUserId
from src.Id.GuildId import GuildId
from src.Manager.NotificationManager import NotificationService

logger = logging.getLogger("KVGG_BOT")
lock = asyncio.Lock()


class ChannelService:

    def __init__(self, client: Client):
        self.client = client
        self.notificationService = NotificationService(self.client)

    @staticmethod
    async def manageKneipe(channel: VoiceChannel):
        """
        Deletes "Kneipe" if there are no members left in the channel.

        :param channel:
        :return:
        """
        if channel.name != "Kneipe":
            return

        if len(channel.members) != 0:
            return

        try:
            await channel.delete(reason="no one in channel anymore")
        except discord.errors.NotFound as error:
            logger.warning("channel not found - maybe because it was deleted beforehand", exc_info=error)

    async def createKneipe(self, invoker: Member, member_1: Member | None, member_2: Member | None) -> str:
        """
        Fetches Paul and Rene or both given members specifically from the guild to move them into a new channel.

        :return:
        """
        memberToMove: list[tuple[Member, VoiceState | None]] = []

        if member_1:
            memberToMove.append((member_1, None))

        if member_2:
            memberToMove.append((member_2, None))

        if not member_1 and not member_2:
            guild = self.client.get_guild(GuildId.GUILD_KVGG.value)

            # overwrite both members to paul and rene
            memberToMove.append((guild.get_member(DiscordUserId.RENE.value), None))
            memberToMove.append((guild.get_member(DiscordUserId.PAUL.value), None))

            if not memberToMove:
                logger.error("couldn't find Paul and Rene")

                return "Es ist ein Fehler aufgetreten."

        for i in range(0, len(memberToMove)):
            if not (voice := memberToMove[i][0].voice):
                logger.debug(f"{memberToMove[i][0].display_name} is not online")

                return f"<@{memberToMove[i][0].id}> ist nicht online."
            else:
                memberToMove[i] = (memberToMove[i][0], voice)

        channel = None

        for member, voice in memberToMove:
            if not channel:
                channel = voice.channel
            else:
                if channel != voice.channel:
                    logger.debug(f"{member.display_name} is not in the same channel as the other member")

                    return f"<@{member.id}> ist nicht im gleichen Channel wie der andere Member."

        if not (invokerVoice := invoker.voice):
            logger.debug(f"{invoker.display_name} is not online -> cant use kneipe")

            return "Du bist aktuell in keinem VoiceChannel! Du kannst diesen Befehl nicht nutzen!"

        # check only with channel here, all are in this channel
        if invokerVoice.channel != channel:
            logger.debug(f"{invoker.display_name} is not in the same channel the chosen members: {memberToMove}")

            return f"Du bist nicht im VoiceChannel von deinen ausgewählten Membern."

        if channel.category.id not in TrackedCategories.getValues():
            logger.debug("category was not withing tracked categories")

            return "Dieser Command funktioniert nicht in deiner aktuellen VoiceChannel-Kategorie."

        if voiceChannel := await self._createNewChannel(channel.category):
            loop = asyncio.get_event_loop()

            try:
                loop.run_until_complete(moveMembers([member for member, _ in memberToMove], voiceChannel))
            except Exception as error:
                logger.error(f"couldn't move members: {memberToMove} into new channel ",
                             exc_info=error, )

                return "Es ist ein Fehler aufgetreten."
            else:
                return f"Die Member wurden in den Channel {voiceChannel.mention} verschoben."
        else:
            return "Es ist ein Fehler aufgetreten."

    async def _createNewChannel(self,
                                category: CategoryChannel,
                                name: str = "Kneipe",
                                userLimit: int = 2) -> VoiceChannel | None:
        """
        Creates a voice-channel in the given category

        :param category: Category from the guild
        :param name: Name of the channel, standard value is "Kneipe"
        :param userLimit: Limits the channel users, standard is 2
        :return:
        """
        if not category:
            logger.critical("no category was given")

            return None

        try:
            voiceChannel = await category.create_voice_channel(name=name, user_limit=userLimit)
        except Exception as error:
            logger.error("couldn't create voice-channel", exc_info=error)

            return None
        else:
            return voiceChannel

    async def checkChannelForMoving(self, member: Member):
        """
        Checks if more than two users are connected to the 'wait for players' channel to move them into the next free
        channel.

        :param member:
        :return:
        """
        async with lock:
            # only move out of this channel
            if member.voice and member.voice.channel.id != ChannelId.CHANNEL_WARTE_AUF_MITSPIELER_INNEN.value:
                return

            # ignore members who are alone
            if len(member.voice.channel.members) < 2:
                return

            if not (channelToMove := self._findFreeChannel()):
                logger.debug("no free channel was found")

                return

            members = member.voice.channel.members
            loop = asyncio.get_event_loop()

            try:
                loop.run_until_complete(moveMembers(members, channelToMove))
            except discord.Forbidden:
                logger.error("dont have rights move the users!")

                return
            except Exception as error:
                logger.error("couldn't move members into new channel", exc_info=error)

                return

            # send DMs after moving all users to prioritize and speed up the moving process
            for user in members:
                await self.notificationService.sendStatusReport(user,
                                                                "Du wurdest verschoben, da ihr mindestens zu "
                                                                "zweit in 'warte auf Mitspieler/innen' wart.")

            logger.debug("moved users out of 'warte auf Mitspieler/innen' due to more than 2 users")

    def _findFreeChannel(self) -> VoiceChannel | None:
        """
        Finds the next empty VoiceChannel in the Gaming-Category.

        :return:
        """
        # list comprehensions are faster than for-loops
        gaming_category = [category for category in self.client.get_guild(GuildId.GUILD_KVGG.value).categories
                           if category.id == TrackedCategories.GAMING.value][0]
        dont_use_channels = [ChannelId.CHANNEL_WARTE_AUF_MITSPIELER_INNEN.value,
                             ChannelId.CHANNEL_GAMING_EIN_DREIVIERTEL.value,
                             ChannelId.CHANNEL_GAMING_ZWEI_LEAGUE_OF_LEGENDS.value,
                             ChannelId.CHANNEL_GAMING_SIEBEN_AMERICA.value,
                             ChannelId.CHANNEL_MARIE_UND_JESPER.value, ]

        for channel in gaming_category.voice_channels:
            if channel.id in dont_use_channels:
                continue

            if len(channel.members) == 0:
                logger.debug(f"{channel.name} ({channel.id}) channel free to move")

                return channel

        logger.debug("all channels are occupied")

        return None
