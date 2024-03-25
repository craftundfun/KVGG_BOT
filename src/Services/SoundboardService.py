import asyncio
import logging
import os
import threading
from asyncio import AbstractEventLoop
from pathlib import Path
from urllib.parse import urlparse

import discord
import requests
from discord import Client, Member, Message
from mutagen.mp3 import MP3

from src.Helper.GetChannelsFromCategory import getVoiceChannelsFromCategoryEnum
from src.Helper.SendDM import sendDM, separator
from src.Id import Categories
from src.Id.GuildId import GuildId
from src.Services.VoiceClientService import VoiceClientService
from src.View.PaginationView import PaginationViewDataItem

logger = logging.getLogger("KVGG_BOT")


class SoundboardService:
    path = './data/sounds/'
    basepath = Path(__file__).parent.parent.parent

    def __init__(self, client: Client):
        self.client = client

        self.voiceClientService = VoiceClientService(self.client)

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

    async def listPersonalSounds(self, ctx: discord.interactions.Interaction) -> list[PaginationViewDataItem]:
        path = os.path.abspath(
            os.path.join(self.basepath, "..", "..", "..", f"{self.basepath}/data/sounds/{ctx.user.id}")
        )

        data = []

        try:
            for index, filepath in enumerate(os.listdir(path), start=1):
                if os.path.isfile(os.path.join(path, filepath)) and filepath[-4:] == '.mp3':
                    seconds = MP3(os.path.join(path, filepath)).info.length
                    data += [PaginationViewDataItem(field_name=f"__**{index}. {filepath}**__",
                                                    field_value=f"**Dauer**: {str(seconds)[:4]} Sekunden")]
        except FileNotFoundError as error:
            logger.warning(f"{ctx.user.display_name} has no sounds uploaded yet", exc_info=error)

            return [PaginationViewDataItem(field_name="Du hast keine Dateien hochgeladen. Wenn du welche hochladen" +
                                                      " möchtest, dann schicke sie mir einfach per DM.")]
        except Exception as error:
            logger.error("problem while reading files from the system", exc_info=error)

            return [PaginationViewDataItem(field_name="Es ist ein Problem aufgetreten.")]
        else:
            return data

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

        try:
            for filepath in os.listdir(path):
                if (os.path.isfile(os.path.join(path, filepath))
                        and filepath[-4:] == ".mp3"
                        and filepath == search):
                    return True
        except FileNotFoundError:
            logger.warning(f"{member.name} has not uploaded a sound yet")

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
                "Deine Datei wird nun verarbeitet..." + separator,
            ),
            loop,
        )

        if response.status_code != 200:
            asyncio.run_coroutine_threadsafe(
                sendDM(
                    self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(authorId),
                    "Beim Speichern deiner Datei ist ein Fehler aufgetreten. Versuche eine andere Datei " +
                    "oder wende dich an uns." + separator,
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
                    "oder wende dich an unserem Support." + separator,
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
                        + separator,
                    ),
                    loop,
                )
                os.remove(filepath)

                return
        except Exception as error:
            logger.debug(f"user {message.author.name} did not upload a mp3", exc_info=error)
            os.remove(filepath)

            # warn user
            asyncio.run_coroutine_threadsafe(
                sendDM(
                    self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(authorId),
                    "Bitte lade eine gültige .mp3 Datei hoch. Sollte der Fehler weiterhin auftreten, melde " +
                    "dich bei unserem Support." + separator
                ),
                loop,
            )

            return

        asyncio.run_coroutine_threadsafe(
            sendDM(
                self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(authorId),
                f"Deine Datei ({os.path.basename(url_parts.path)}) wurde erfolgreich gespeichert."
                + separator,
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

            return ("Der Sound existiert nicht. Du kannst den Sound hochladen indem du ihn mir als Privatnachricht "
                    "schickst.")

        if not (voiceState := member.voice):
            return "Du bist mit keinem Channel verbunden!"

        if voiceState.channel not in getVoiceChannelsFromCategoryEnum(self.client, Categories.TrackedCategories):
            return "Dein Channel / die Kategorie ist nicht berechtigt Sounds abzuspielen."

        filepath = f"{member.id}/{sound}"

        if not await self.voiceClientService.play(voiceState.channel, self.path + filepath, ctx, False):
            return "Der Bot spielt aktuell schon etwas ab oder es gab ein Problem."

        return "Dein gewählter Sound wurde abgespielt."
