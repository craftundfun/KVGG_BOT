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

from src.Helper.DictionaryFuntionKeyDecorator import validateKeys
from src.Helper.GetChannelsFromCategory import getVoiceChannelsFromCategoryEnum
from src.Helper.SendDM import sendDM
from src.Id import Categories
from src.Id.GuildId import GuildId
from src.Services.VoiceClientService import VoiceClientService

logger = logging.getLogger("KVGG_BOT")


class SoundboardService:
    path = './data/sounds/'
    basepath = Path(__file__).parent.parent.parent

    def __init__(self, client: Client):
        self.client = client

    @validateKeys
    async def deletePersonalSound(self, ctx: discord.interactions.Interaction, row: int) -> str:
        """
        Deletes the file at position row.

        :param ctx:
        :param row:
        :return:
        """
        path = os.path.abspath(
            os.path.join(self.basepath, "..", "..", "..", f"{self.basepath}/data/sounds/{ctx.user.id}")
        )

        if not (0 <= row - 1 < len((dir := os.listdir(path)))):
            logger.debug(f"user chose row {row - 1}, but that was not possible")

            return "Deine Auswahl steht nicht zur Verfügung!"

        try:
            os.remove(os.path.join(path, dir[row - 1]))
        except FileNotFoundError as error:
            logger.error("user has no sounds uploaded yet", exc_info=error)

            return "Diese Datei hat nicht existiert."
        except Exception as error:
            logger.error("problem while reading files from the system", exc_info=error)

            return "Es ist ein Problem aufgetreten."
        else:
            return "Deine Datei wurde erfolgreich gelöscht."

    @validateKeys
    async def listPersonalSounds(self, ctx: discord.interactions.Interaction) -> str:
        path = os.path.abspath(
            os.path.join(self.basepath, "..", "..", "..", f"{self.basepath}/data/sounds/{ctx.user.id}")
        )
        answer = "Du hast folgende Sounds hochgeladen:\n\n"

        try:
            for index, filepath in enumerate(os.listdir(path), start=1):
                if os.path.isfile(os.path.join(path, filepath)) and filepath[-4:] == '.mp3':
                    seconds = MP3(os.path.join(path, filepath)).info.length
                    answer += f"{index}. {filepath} - {str(seconds)[:4]} Sekunden\n"
        except FileNotFoundError as error:
            logger.warning("user has no sounds uploaded yet", exc_info=error)

            return ("Du hast keine Dateien hochgeladen. Wenn du welche hochladen möchtest, "
                    "dann schicke sie mir einfach per DM.")
        except Exception as error:
            logger.error("problem while reading files from the system", exc_info=error)

            return "Es ist ein Problem aufgetreten."
        else:
            return answer

    def searchInPersonalFiles(self, member: discord.Member, search: str) -> bool:
        """
        Checks if Sound is in the sound directory of the user.

        :param member: Member, who used the command
        :param search: Name of the mp3 File
        :return:
        """
        path = os.path.abspath(
            os.path.join(self.basepath, "..", "..", "..", f"{self.basepath}/data/sounds/{member.id}")
        )

        for filepath in os.listdir(path):
            if (os.path.isfile(os.path.join(path, filepath))
                    and filepath[-4:] == ".mp3"
                    and filepath == search):
                return True

        return False

    def downloadFileFromURL(self, message: Message, url: str, loop: AbstractEventLoop):
        """
        Downloads file from a direct message and do security checks

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
            loop,
        )

        if response.status_code != 200:
            asyncio.run_coroutine_threadsafe(
                sendDM(
                    self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(authorId),
                    "Beim Speichern deiner Datei ist ein Fehler aufgetreten. Versuche eine andere Datei " +
                    "oder wende dich an uns."
                ),
                loop,
            )

            return

        os.makedirs(f"{self.basepath}/data/sounds/{authorId}/", exist_ok=True)

        filepath = f"{self.basepath}/data/sounds/{authorId}/{os.path.basename(url_parts.path)}"

        try:
            with open(filepath, 'wb+') as file:
                file.write(response.content)
        except Exception as error:
            logger.error(f"couldn't save .mp3 in {filepath}", exc_info=error)

            # Inform User
            asyncio.run_coroutine_threadsafe(
                sendDM(
                    self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(authorId),
                    "Beim Speichern deiner Datei ist ein Fehler aufgetreten. Versuch eine andere Datei " +
                    "oder wende dich an unserem Support."
                ),
                loop,
            )

            return
        else:
            logger.debug(f"mp3 written in {filepath}")

        try:
            mp3 = MP3(filepath)

            if mp3.info.length > 20:
                asyncio.run_coroutine_threadsafe(
                    sendDM(
                        self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(authorId),
                        "Bitte lade eine .mp3 Datei hoch die weniger als 20 Sekunden lang ist."
                    ),
                    loop,
                )
                os.remove(filepath)

                return
        except Exception as error:
            logger.error(f"user {message.author.name} did not upload a mp3", exc_info=error)
            os.remove(filepath)

            # warn user
            asyncio.run_coroutine_threadsafe(
                sendDM(
                    self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(authorId),
                    "Bitte lade eine gültige .mp3 Datei hoch. Sollte der Fehler weiterhin auftreten, melde " +
                    "dich bei unserem Support."
                ),
                loop,
            )

            return

        asyncio.run_coroutine_threadsafe(
            sendDM(
                self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(authorId),
                f"Deine Datei ({os.path.basename(url_parts.path)}) wurde erfolgreich gespeichert."
            ),
            loop,
        )
        logger.debug("MP3 was saved successfully")

    async def manageDirectMessage(self, message: Message):
        """
        Checks for author in a message and starts file-download

        :param message: Message to check
        :return:
        """
        if not message.author:
            logger.warning("DM had no author given")

            return

        attachments = message.attachments
        loop = asyncio.get_event_loop()

        for attachment in attachments:
            url = attachment.url

            threading.Thread(target=self.downloadFileFromURL, args=(message, url, loop)).start()
            logger.debug(f"started thread for downloading '{url}'")

    @validateKeys
    async def playSound(self, member: Member, sound: str, ctx: discord.interactions.Interaction) -> str:
        """
        Starts to play the specified sounds in the channel from the member.

        :param ctx: Interaction
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

        if not await VoiceClientService(self.client).play(voiceState.channel, self.path + filepath, ctx, False):
            return "Der Bot spielt aktuell schon etwas ab oder es gab ein Problem."

        return "Dein gewählter Sound wurde abgespielt."

    @DeprecationWarning
    async def __playSound(self, channel: VoiceChannel, filepath: str, ctx: discord.interactions.Interaction) -> bool:
        """
        Tries to play the sound in the given channel.

        :param channel: Channel to play the sound in
        :param filepath: sound to play
        :param ctx: Interaction to tell the user the sound is playing
        :return:
        """
        try:
            voiceClient: VoiceClient = await channel.connect()
        except ClientException:
            logger.warning("already connected to a voicechannel")

            return False
        except Exception as error:
            logger.error("an error occurred while joining a voice channel", exc_info=error)

            return False

        if voiceClient.is_playing():
            logger.debug("currently playing a sound")

            return False

        file = FFmpegPCMAudio(source=(filepath := self.path + filepath))
        duration = MP3(filepath).info.length

        try:
            voiceClient.play(file)
            await ctx.followup.send("Dein gewählter Sound wird abgespielt.")

            await sleep(duration)
        except Exception as error:
            logger.error("a problem occurred during playing a sound in %s" % channel.name, exc_info=error)

            return False
        else:
            return True
        finally:
            await voiceClient.disconnect()

    @DeprecationWarning
    @validateKeys
    async def stop(self, member: Member) -> str:
        """
        If the VoiceClient is active and the bot and user are in the same channel, the bot will disconnect from the
        channel.

        :param member:
        :return:
        """
        if not (voiceState := member.voice):
            logger.debug("%s was not in a channel" % member.name)

            return "Du befindest dich aktuell in keinem VoiceChannel!"

        voiceClient = self.client.get_guild(GuildId.GUILD_KVGG.value).voice_client

        if not voiceClient:
            logger.debug("bot is not connected to a voice channel")

            return "Der Bot ist aktuell in keinem Channel aktiv."

        channelBot = voiceClient.channel

        if voiceState.channel != channelBot:
            logger.debug("%s and the bot are not connected to the same channel" % member.name)

            return "Du befindest nicht im selben Channel wie der Bot!"

        await voiceClient.disconnect(force=True)
        logger.debug("sound was stopped by %s" % member.name)

        return "Das Abspielen des Sounds wurde beendet."
