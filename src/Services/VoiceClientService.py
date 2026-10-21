import logging
from asyncio import sleep

from discord import Client, VoiceChannel, VoiceClient, FFmpegPCMAudio, Member, VoiceState
from discord.interactions import Interaction

from src.Helper.GetChannelsFromCategory import getVoiceChannelsFromCategoryEnum
from src.Id.Categories import TrackedCategories

logger = logging.getLogger("KVGG_BOT")


class VoiceClientService:
    _self = None
    voiceClient: VoiceClient | None = None
    # CTX to tell the user his /her playing of a sound is getting cancelled due to a forced sound
    voiceClientCorrespondingCTX: Interaction | None = None
    # if the bot should hang up after playing a sound
    hangUp = True

    def __init__(self, client: Client):
        self.client = client

    def __new__(cls, *args, **kwargs):
        """
        Singleton-Pattern
        """
        if not cls._self:
            cls._self = super().__new__(cls)

        return cls._self

    async def play(self, channel: VoiceChannel, pathToSound: str, ctx: Interaction = None, force: bool = False,
                   loop: bool = False) -> bool:
        """
        Plays the given sound. If the sound is forced to play, the bot stops the current replay and plays the new given
        sound.
        """
        # already playing something and not forced to play the new sound
        if self.voiceClient and not force:
            logger.debug("cant play sound, bot is in use")

            return False

        if not (allowedChannels := getVoiceChannelsFromCategoryEnum(self.client, TrackedCategories)):
            logger.warning("couldn't fetch any channels from client")

            return False
        elif channel not in allowedChannels:
            logger.warning("channel not in allowed spectrum")

            return False

        # create VoiceClient if it does not exist yet
        if not self.voiceClient:
            try:
                self.voiceClient = await channel.connect()
            except Exception as error:
                logger.debug("something went wrong while connecting to a voice-channel", exc_info=error)

                return False
        # if it exists and is forced to play something, stop it
        elif force:
            self.voiceClient.stop()

            # switch to the correct channel
            if self.voiceClient.channel != channel:
                try:
                    await self.voiceClient.move_to(channel)
                except Exception as error:
                    logger.error("couldn't move bot to channel", exc_info=error)

                    return False

        # tell the user about the cancellation of the sound
        if force and self.voiceClientCorrespondingCTX:
            await self.voiceClientCorrespondingCTX.followup.send("Das Abspielen deines Sounds wurde für einen "
                                                                 "priorisierten Sound abgebrochen.")
            # don't let lower priority sounds hang up if a forced sound is played
            self.hangUp = False

        # save ctx to current voice-client
        self.voiceClientCorrespondingCTX = ctx

        before_options = "-stream_loop -1" if loop else None
        file = FFmpegPCMAudio(source=pathToSound, before_options=before_options, options="-filter:a loudnorm")

        try:
            self.voiceClient.play(file)

            if ctx:
                if loop:
                    await ctx.followup.send("Dein gewählter Sound wird in einer Endlosschleife abgespielt.")
                else:
                    await ctx.followup.send("Dein gewählter Sound wird abgespielt.")

            # wait dynamically as long as this audio source is playing (reacts immediately to stop/kick)
            while self.voiceClient and self.voiceClient.is_playing() and self.voiceClient.source == file:
                await sleep(0.25)

            # short buffer at the natural end of a non-looped sound to avoid clipping
            if not loop and self.voiceClient and self.hangUp:
                await sleep(0.25)

            return True
        except Exception as error:
            logger.error(f"couldn't play sound in path {pathToSound}", exc_info=error)

            return False
        finally:
            # if the sound was forced, give permission to hang up for low priority sounds
            if force and not self.hangUp:
                self.hangUp = True

            if self.voiceClient and self.hangUp:
                vc = self.voiceClient
                self.voiceClient = None
                await vc.disconnect()

            if self.voiceClientCorrespondingCTX == ctx:
                self.voiceClientCorrespondingCTX = None

    async def stop(self, member: Member) -> str:
        """
        If the VoiceClient is active and the bot and user are in the same channel, the bot will disconnect from the
        channel.
        """
        if not (voiceState := member.voice):
            logger.debug(f"{member.name} was not in a channel")

            return "Du befindest dich aktuell in keinen VoiceChannel!"

        if not self.voiceClient:
            logger.debug("bot is not connected to a voice channel")

            return "Der Bot ist aktuell in keinem Channel aktiv."

        if voiceState.channel != self.voiceClient.channel:
            logger.debug(f"{member.display_name} and the bot are not connected to the same channel")

            return "Du befindest nicht im selben Channel wie der Bot!"

        vc = self.voiceClient
        self.voiceClient = None
        await vc.disconnect(force=True)

        if self.voiceClientCorrespondingCTX:
            ctx = self.voiceClientCorrespondingCTX
            self.voiceClientCorrespondingCTX = None
            await ctx.followup.send(f"Das Abspielen deines Sounds wurde von {member.display_name} gestoppt!")

        return "Das Abspielen des Sounds wurde beendet."

    async def leaveIfChannelEmpty(self, channel: VoiceChannel):
        """
        Disconnects the bot if it is currently in the given channel and no human members are left.
        """
        if not self.voiceClient or self.voiceClient.channel != channel:
            return

        if not any(not member.bot for member in channel.members):
            logger.debug(f"No members left in {channel.name}, disconnecting VoiceClient")

            vc = self.voiceClient
            self.voiceClient = None
            await vc.disconnect(force=True)

            if self.voiceClientCorrespondingCTX:
                ctx = self.voiceClientCorrespondingCTX
                self.voiceClientCorrespondingCTX = None
                await ctx.followup.send(
                    "Das Abspielen des Sounds wurde beendet, da sich niemand mehr im Channel befindet."
                )

    async def handleBotVoiceStateUpdate(self, before: VoiceState, after: VoiceState):
        """
        Handles cases where the bot itself is manually disconnected or moved by an admin.
        """
        if not self.voiceClient:
            return

        # Fall 1: Bot wurde manuell aus dem Channel gekickt (Verbindung getrennt)
        if before.channel and not after.channel:
            logger.info("Bot was manually disconnected from voice channel")

            vc = self.voiceClient
            self.voiceClient = None
            vc.stop()
            # interne VoiceClient-Session in discord.py sauber aufräumen
            await vc.disconnect(force=True)

            if self.voiceClientCorrespondingCTX:
                ctx = self.voiceClientCorrespondingCTX
                self.voiceClientCorrespondingCTX = None
                await ctx.followup.send(
                    "Das Abspielen deines Sounds wurde abgebrochen, da der Bot aus dem Channel getrennt wurde."
                )

        # Fall 2: Bot wurde in einen anderen Channel verschoben
        elif before.channel and after.channel and before.channel != after.channel:
            logger.info(f"Bot was moved from {before.channel.name} to {after.channel.name}")

            allowedChannels = getVoiceChannelsFromCategoryEnum(self.client, TrackedCategories)

            # Wenn der Ziel-Channel nicht erlaubt ist, sofort trennen
            if not allowedChannels or after.channel not in allowedChannels:
                logger.warning("Bot was moved into an unallowed channel, disconnecting")

                vc = self.voiceClient
                self.voiceClient = None
                await vc.disconnect(force=True)

                if self.voiceClientCorrespondingCTX:
                    ctx = self.voiceClientCorrespondingCTX
                    self.voiceClientCorrespondingCTX = None
                    await ctx.followup.send(
                        "Das Abspielen wurde beendet, da der Bot in einen nicht erlaubten Channel verschoben wurde."
                    )
                return

            # Prüfen, ob im neuen Ziel-Channel überhaupt echte User sitzen (sonst direkt wieder verlassen)
            await self.leaveIfChannelEmpty(after.channel)