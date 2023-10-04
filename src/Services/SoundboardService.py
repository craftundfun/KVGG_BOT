import asyncio
import concurrent.futures
import logging
import os
import threading
from asyncio import sleep, AbstractEventLoop
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse

import discord
import requests
from discord import Client, VoiceChannel, VoiceClient, FFmpegPCMAudio, Member, ClientException, Message
from discord.app_commands import Choice
from mutagen.mp3 import MP3

from src.Helper.GetChannelsFromCategory import getVoiceChannelsFromCategoryEnum
from src.Helper.SendDM import sendDM
from src.Id import Categories
from src.Id.GuildId import GuildId

logger = logging.getLogger("KVGG_BOT")


class Sounds(Enum):
    EGAL = "egal.mp3"


def run_event_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

class SoundboardService:
    path = './data/sounds/'
    basepath = Path(__file__).parent.parent.parent

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

    def downloadFileFromURL(self, message: Message, url: str, loop: AbstractEventLoop):
        authorId = message.author.id
        print("drin")
        url_parts = urlparse(url)
        response = requests.get(url)

        if response.status_code == 200:
            os.makedirs(f"{self.basepath}/data/sounds/{authorId}/", exist_ok=True)

            with open(f"{self.basepath}/data/sounds/{authorId}/{os.path.basename(url_parts.path)}",
                      'wb+') as file:
                file.write(response.content)
                print("geschrieben in " + f"{self.basepath}/data/sounds/{authorId}/{os.path.basename(url_parts.path)}")

                asyncio.run_coroutine_threadsafe(
                    sendDM(self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(authorId), "FERTIG"),
                    loop
                )

    async def manageDirectMessage(self, message: Message):
        if not (author := message.author):
            logger.debug("DM had no author given")

        # url = "https://speed.hetzner.de/100MB.bin"
        url = "https://speed.hetzner.de/1GB.bin"
        loop = asyncio.get_event_loop()

        job_thread = threading.Thread(target=self.downloadFileFromURL, args=(message, url, loop))
        job_thread.start()

        # thread = threading.Thread(target=asyncio.run, args=(self.downloadFileFromURL(message, url, loop, ),))
        # thread.start()

        print("return")


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
