import logging
import os
from asyncio import sleep
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse

import discord
import requests
from discord import Client, VoiceChannel, VoiceClient, FFmpegPCMAudio, Member, ClientException, Message
from discord.app_commands import Choice
from mutagen.mp3 import MP3

from src.Helper.GetChannelsFromCategory import getVoiceChannelsFromCategoryEnum
from src.Id import Categories

logger = logging.getLogger("KVGG_BOT")


class Sounds(Enum):
    EGAL = "egal.mp3"


class SoundboardService:
    path = './data/sounds/'

    def __init__(self, client: Client):
        self.client = client

    @staticmethod
    async def getPersonalSounds(interaction: discord.Interaction, current: str, _) -> list[Choice[str]]:
        print(_)
        member = interaction.user.id
        basepath = os.path.dirname(__file__)
        path = os.path.abspath(os.path.join(basepath, "..", "..", "..", f"{basepath}/data/sounds/{member}"))
        print(path)

        files = []

        for filepath in os.listdir(path):
            if os.path.isfile(os.path.join(path, filepath)):
                files.append(filepath)

        return [Choice(name=file, value=file) for file in files if file.lower() in current.lower()]

    async def manageDirectMessage(self, message: Message):
        if not (author := message.author):
            logger.debug("DM had no author given")

        basepath = Path(__file__).parent.parent.parent

        for attachment in message.attachments:
            url = attachment.url
            url_parts = urlparse(url)
            download = requests.get(url)

            if download.status_code == 200:
                os.makedirs(f"{basepath}/data/sounds/{author.id}/", exist_ok=True)

                with open(f"{basepath}/data/sounds/{author.id}/{os.path.basename(url_parts.path)}", 'wb+') as file:
                    file.write(download.content)

    async def play(self, member: Member, sound: str) -> str:
        """
        Starts to play the specified sounds in the channel from the member.

        :param member: Member, who used the command
        :param sound: Sound to play
        :return:
        """
        match sound:
            case Sounds.EGAL.value:
                sound = Sounds.EGAL
            case _:
                logger.warning("undefined enum entry was reached")

                return "Es gab ein Problem."

        if not (voiceState := member.voice):
            return "Du bist mit keinem Channel verbunden!"

        if voiceState.channel not in getVoiceChannelsFromCategoryEnum(self.client, Categories.TrackedCategories):
            return "Dein Channel / die Kategorie ist nicht berechtigt Sounds abzuspielen."

        if not await self.__playSound(voiceState.channel, sound):
            return "Der Bot spielt aktuell schon etwas ab oder es gab ein Problem."

        return "Dein gewählter Sound wurde abgespielt."

    async def __playSound(self, channel: VoiceChannel, sound: Sounds) -> bool:
        """
        Tries to play the sound in the given channel.

        :param channel: Channel to play the sound in
        :param sound: sound to play
        :return:
        """
        try:
            voiceClient: VoiceClient = await channel.connect()
        except ClientException as error:
            logger.warning("already connected to a voicechannel", exc_info=error)

            return False
        except Exception as error:
            logger.error("an error occured while joining a voice channel", exc_info=error)

            return False

        if voiceClient.is_playing():
            logger.debug("currently playing a sound")

            return False

        file = FFmpegPCMAudio(source=(filepath := self.path + sound.value))
        duration = MP3(filepath).info.length

        try:
            voiceClient.play(file)

            await sleep(duration)
        except Exception as error:
            logger.error("a problem occurred during playing a sound in %s" % channel.name, exc_info=error)

            return False
        else:
            return True
        finally:
            await voiceClient.disconnect()
