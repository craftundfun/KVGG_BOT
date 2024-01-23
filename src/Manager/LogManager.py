import logging
from datetime import datetime
from enum import Enum

import discord
from discord import Client, Member, Embed, VoiceState

from src.Id.ChannelId import ChannelId

logger = logging.getLogger("KVGG_BOT")


class Events(Enum):
    JOINED_VOICE_CHAT = (0, 204, 0)  # green
    LEFT_VOICE_CHANNEL = (255, 0, 0)  # red
    SWITCHED_VOICE_CHANNEL = (255, 128, 0)  # orange

    SELF_MUTE = (255, 133, 133)  # light red
    SELF_NOT_MUTE = (153, 255, 153)  # light green
    SELF_DEAF = (254, 133, 133)  # light red
    SELF_NOT_DEAF = (152, 255, 153)  # light green

    MUTE = (153, 0, 0)  # dark red
    NOT_MUTE = (0, 153, 0)  # dark green
    DEAF = (154, 0, 0)  # dark red
    NOT_DEAF = (0, 154, 0)  # dark green

    START_STREAM = (0, 0, 255)  # dark blue
    END_STREAM = (204, 0, 204)  # violet
    START_WEBCAM = (0, 0, 254)  # dark blue
    END_WEBCAM = (205, 0, 205)  # violet


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

            case Events.SWITCHED_VOICE_CHANNEL:
                title = (f"{member.display_name} ist von `{voiceStateBefore.channel.name}` nach "
                         f"`{voiceStateAfter.channel.name}` gewechselt.")

            case Events.LEFT_VOICE_CHANNEL:
                title = f"{member.display_name} hat den Channel `{voiceStateBefore.channel.name}` verlassen."

            case Events.START_STREAM:
                title = f"{member.display_name} hat seinen / ihren Stream gestartet."

            case Events.END_STREAM:
                title = f"{member.display_name} hat seinen / ihren Stream beendet."

            case Events.START_WEBCAM:
                title = f"{member.display_name} hat seine / ihre Webcam gestartet."

            case Events.END_WEBCAM:
                title = f"{member.display_name} hat seine / ihre Webcam beendet."

            case Events.SELF_MUTE:
                title = f"{member.display_name} hat sich muted."

            case Events.SELF_NOT_MUTE:
                title = f"{member.display_name} hat sich entmuted."

            case Events.SELF_DEAF:
                title = f"{member.display_name} hat sich deafened."

            case Events.SELF_NOT_DEAF:
                title = f"{member.display_name} hat sich nicht mehr deafened."

            case Events.MUTE:
                title = f"{member.display_name} wurde stummgeschaltet."

            case Events.NOT_MUTE:
                title = f"{member.display_name} wurde nicht mehr stummgeschaltet."

            case Events.DEAF:
                title = f"{member.display_name} wurde deafened."

            case Events.NOT_DEAF:
                title = f"{member.display_name} wurde nicht mehr deafened."

            case _:
                logger.error("undefined enum-entry was reached")

                return

        embed = Embed(
            title=title,
            color=discord.Color.from_rgb(*event.value),
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
