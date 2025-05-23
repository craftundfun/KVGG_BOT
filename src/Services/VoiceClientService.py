import logging
from asyncio import sleep

from discord import Client, VoiceChannel, VoiceClient, FFmpegPCMAudio, Member
from discord.interactions import Interaction
from mutagen.mp3 import MP3

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

    async def play(self, channel: VoiceChannel, pathToSound: str, ctx: Interaction = None, force: bool = False) -> bool:
        """
        Plays the given sound. If the sound is forced to play, the bot stops the current replay and plays the new given
        sound.

        :param channel:
        :param pathToSound:
        :param ctx:
        :param force:
        :return:
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

        file = FFmpegPCMAudio(source=pathToSound, options="-filter:a loudnorm")
        duration = MP3(pathToSound).info.length

        try:
            self.voiceClient.play(file)

            if ctx:
                await ctx.followup.send("Dein gewählter Sound wird abgespielt.")

            # sleep 250ms longer to avoid hiccups at the start and the following abrupt ending
            await sleep(duration + 0.25)

            return True
        except Exception as error:
            logger.error(f"couldn't play sound in path {pathToSound}", exc_info=error)

            return False
        finally:
            # if the sound was forced, give permission to hang up for low priority sounds
            if force and not self.hangUp:
                self.hangUp = True

            if self.voiceClient and self.hangUp:
                await self.voiceClient.disconnect()
                self.voiceClient = None

            if self.voiceClientCorrespondingCTX:
                self.voiceClientCorrespondingCTX = None

    async def stop(self, member: Member) -> str:
        """
        If the VoiceClient is active and the bot and user are in the same channel, the bot will disconnect from the
        channel.

        :param member:
        :return:
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

        await self.voiceClient.disconnect(force=True)
        self.voiceClient = None

        if self.voiceClientCorrespondingCTX:
            await self.voiceClientCorrespondingCTX.followup.send(f"Das Abspielen deines Sounds wurde von "
                                                                 f"{member.display_name} gestoppt!")

            self.voiceClientCorrespondingCTX = None

        return "Das Abspielen des Sounds wurde beendet."
