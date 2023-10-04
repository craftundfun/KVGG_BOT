import asyncio
import logging
import os
import threading
from asyncio import sleep, AbstractEventLoop
from pathlib import Path
from urllib.parse import urlparse

import discord
import requests
from discord import Client, VoiceChannel, VoiceClient, FFmpegPCMAudio, Member, ClientException, Message
from mutagen.mp3 import MP3

from src.Helper.GetChannelsFromCategory import getVoiceChannelsFromCategoryEnum
from src.Helper.SendDM import sendDM
from src.Id import Categories
from src.Id.GuildId import GuildId

logger = logging.getLogger("KVGG_BOT")

def run_event_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


class SoundboardService:
    path = './data/sounds/'
    basepath = Path(__file__).parent.parent.parent

    def __init__(self, client: Client):
        self.client = client

    def searchInPersonalFiles(self, member: discord.Member, search: str) -> bool:
        """
        Checks if Sound is in the sound direcory of the user.

        :param member: Member, who used the command
        :param search: Name of the mp3 File
        :return:
        """
        path = os.path.abspath(
            os.path.join(self.basepath, "..", "..", "..", f"{self.basepath}/data/sounds/{member.id}"))

        for filepath in os.listdir(path):
            if os.path.isfile(os.path.join(path, filepath)) and filepath[-4:] == '.mp3' and filepath == search:
                return True

        return False

    def downloadFileFromURL(self, message: Message, url: str, loop: AbstractEventLoop):
        """
        Downloads file from direct message and does security checks

        :param message: Message from the user
        :param url: Url to the file
        :param loop: EventLoop from the dc-bot to return a message on error/success
        :return:
        """
        authorId = message.author.id
        url_parts = urlparse(url)
        response = requests.get(url)

        asyncio.run_coroutine_threadsafe(
            sendDM(
                self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(authorId),
                "Deine Datei wird nun verarbeitet..."
            ),
            loop
        )

        if response.status_code == 200:
            os.makedirs(f"{self.basepath}/data/sounds/{authorId}/", exist_ok=True)

            filepath = f"{self.basepath}/data/sounds/{authorId}/{os.path.basename(url_parts.path)}"

            try:
                with open(filepath, 'wb+') as file:
                    file.write(response.content)
                    logger.debug(f"mp3 written in {filepath}")
            except Exception as error:
                logger.error(f"couldnt save .mp3 in {filepath}", exc_info=error)

                # Inform User
                asyncio.run_coroutine_threadsafe(
                    sendDM(
                        self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(authorId),
                        "Beim Speichern deiner Datei ist ein Fehler aufgetreten. Versuch eine andere Datei " +
                        "oder wende dich an unserem Support."
                    ),
                    loop
                )

                return

            try:
                mp3 = MP3(filepath)

                if mp3.info.length > 20:
                    asyncio.run_coroutine_threadsafe(
                        sendDM(
                            self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(authorId),
                            "Bitte lad eine .mp3 Datei hoch die weniger als 20 Sekunden lang ist."
                        ),
                        loop
                    )
                    os.remove(filepath)

                    return
            except Exception as error:
                logger.error(f"user {message.author.name} did not upload mp3", exc_info=error)
                os.remove(filepath)

                # Kill User
                asyncio.run_coroutine_threadsafe(
                    sendDM(
                        self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(authorId),
                        "Bitte lad eine gültige .mp3 Datei hoch. Sollte der Fehler weiterhin auftreten melde " +
                        "dich bei unserem Support."
                    ),
                    loop
                )

                return

            asyncio.run_coroutine_threadsafe(
                sendDM(
                    self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(authorId),
                    "Deine Datei wurde erfolgreich gespeichert."
                ),
                loop
            )
        else:
            asyncio.run_coroutine_threadsafe(
                sendDM(
                    self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(authorId),
                    "Beim Speichern deiner Datei ist ein Fehler aufgetreten. Versuch eine andere Datei " +
                    "oder wende dich an unserem Support."
                ),
                loop
            )

    async def manageDirectMessage(self, message: Message):
        """
        Checks for author in message and starts file-download

        :param message: Message to check
        :return:
        """
        if not message.author:
            logger.debug("DM had no author given")

        url = message.attachments[0].url
        loop = asyncio.get_event_loop()

        job_thread = threading.Thread(target=self.downloadFileFromURL, args=(message, url, loop))
        job_thread.start()

    async def play(self, member: Member, sound: str) -> str:
        """
        Starts to play the specified sounds in the channel from the member.

        :param member: Member, who used the command
        :param sound: Sound to play
        :return:
        """
        if not self.searchInPersonalFiles(member=member, search=sound):
            logger.debug(f"file {sound} not found")

            return "Der Sound existiert nicht. Du kannst den Sound hochladen indem du ihn mir als PN schickst."

        if not (voiceState := member.voice):
            return "Du bist mit keinem Channel verbunden!"

        if voiceState.channel not in getVoiceChannelsFromCategoryEnum(self.client, Categories.TrackedCategories):
            return "Dein Channel / die Kategorie ist nicht berechtigt Sounds abzuspielen."

        filepath = f"{member.id}/{sound}"

        if not await self.__playSound(voiceState.channel, filepath):
            return "Der Bot spielt aktuell schon etwas ab oder es gab ein Problem."

        return "Dein gewählter Sound wurde abgespielt."

    async def __playSound(self, channel: VoiceChannel, filepath: str, ) -> bool:
        """
        Tries to play the sound in the given channel.

        :param channel: Channel to play the sound in
        :param filepath: sound to play
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

        file = FFmpegPCMAudio(source=(filepath := self.path + filepath))
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
