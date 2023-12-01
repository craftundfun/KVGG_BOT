import logging
from datetime import datetime
from enum import Enum

import discord
from discord import Client, Member, Embed, VoiceState

from src.Id.ChannelId import ChannelId

logger = logging.getLogger("KVGG_BOT")


class Events(Enum):
    JOINED_VOICE_CHAT = 0
    LEFT_VOICE_CHANNEL = 1
    SWITCHED_VOICE_CHANNEL = 2


class LogService:

    def __init__(self, client: Client):
        """
        :param client: Discord-Client
        """
        self.client = client
        self.channel = self.client.get_channel(ChannelId.CHANNEL_PROTOKOLLE.value)

    async def sendLog(self, member: Member, voiceStates: (VoiceState, VoiceState), event: Events):
        """
        Creates a fitting embed to the occurred event and sends it in the protocol channel.

        :param member: Member who raised the event
        :param voiceStates: Tuple of the voiceState before and after
        :param event: The event that occurred
        """
        voiceStateBefore: VoiceState = voiceStates[0]
        voiceStateAfter: VoiceState = voiceStates[1]
        profilePicture = member.avatar.url

        match event:
            case Events.JOINED_VOICE_CHAT:
                if not voiceStateAfter.channel:
                    logger.warning("join channel was None")

                    return

                title = f"{member.display_name} ist dem Sprachkanal `{voiceStateAfter.channel.name}` beigetreten."
                color = discord.Color.green()
            case Events.SWITCHED_VOICE_CHANNEL:
                title = (f"{member.display_name} ist von `{voiceStateBefore.channel.name}` nach "
                         f"`{voiceStateAfter.channel.name}` gewechselt.")
                color = discord.Color.orange()
            case Events.LEFT_VOICE_CHANNEL:
                title = f"{member.display_name} hat den Channel `{voiceStateBefore.channel.name}` verlassen."
                color = discord.Color.red()
            case _:
                logger.error("undefined enum-entry was reached")

                return

        embed = Embed(
            title=title,
            color=color,
        )
        embed.set_author(name=member.name, icon_url=profilePicture)
        embed.set_footer(text=f"KVGG")
        embed.timestamp = datetime.now()

        # channel can be None due to the start order of the bot
        if self.channel:
            try:
                await self.channel.send(embed=embed)
            except Exception as error:
                logger.error("couldn't send embed into channel", exc_info=error)

                return
        else:
            self.channel = self.client.get_channel(ChannelId.CHANNEL_PROTOKOLLE.value)

            if not self.channel:
                logger.error("Protokolle-channel is None")

            try:
                await self.channel.send(embed=embed)
            except Exception as error:
                logger.error("couldn't send embed into channel", exc_info=error)

                return

            return
