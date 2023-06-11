from __future__ import annotations

import json

from src.Helper import WriteSaveQuery
from src.Id.ChatCommand import ChatCommand
from src.Id.RoleId import RoleId
from src.Helper import ReadParameters as rp
from src.Helper.ReadParameters import Parameters as parameters
from discord import Message, Client

import string
import discord
import mysql.connector
import requests


class ProcessUserInput:
    databaseConnection = None
    discord = None

    def __init__(self, discord: Client):
        self.databaseConnection = mysql.connector.connect(
            user=rp.getParameter(parameters.USER),
            password=rp.getParameter(parameters.PASSWORD),
            host=rp.getParameter(parameters.HOST),
            database=rp.getParameter(parameters.NAME),
        )
        self.discord = discord

    async def processMessage(self, message: Message):
        if message.channel.guild.id is None or message.author.id is None:
            return

        cursor = self.databaseConnection.cursor()
        query = "SELECT * FROM discord WHERE user_id = %s"

        cursor.execute(query, ([message.author.id]))
        dcUserDb = cursor.fetchall()

        if not dcUserDb:
            pass  # TODO create DiscordUser
            return

        dcUserDb = dict(zip(cursor.column_names, dcUserDb[0]))
        # print(dcUserDb['message_count_all_time'])
        # if message.channel.id != ChannelId.ChannelId.CHANNEL_BOT_TEST_ENVIRONMENT.value:
        dcUserDb['message_count_all_time'] = dcUserDb['message_count_all_time'] + 1000000
        # TODO addExperience

        query = WriteSaveQuery.writeSaveQuery(
            rp.getParameter(rp.Parameters.NAME) + ".discord",
            str(dcUserDb['id']),
            dcUserDb
        )

        cursor.execute(query[0], query[1])
        self.databaseConnection.commit()

        await self.processCommand(message)

    async def processCommand(self, message: Message):
        command = message.content

        if not command.startswith('!'):
            pass  # TODO checkForNewQuote

            return

        command = self.getCommand(command)

        if ChatCommand.JOKE == command:
            await self.answerJoke(message)
        elif ChatCommand.MOVE == command:
            await self.moveUsers(message)

    def getCommand(self, command: string) -> ChatCommand | None:
        command = command.split(' ')[0]

        for enum_command in ChatCommand:
            if enum_command.value == command:
                return enum_command

        return None

    # TODO maybe improve
    def hasUserWantedRoles(self, author: Message.author, *roles) -> bool:
        for role in roles:
            id = role.value
            rolesFromAuthor = author.roles

            for roleAuthor in rolesFromAuthor:
                if id == roleAuthor.id:
                    return True

        return False

    async def answerJoke(self, message: Message):
        payload = {
            'language': 'de',
            'category': 'programmierwitze'
        }

        answer = requests.get(
            'https://witzapi.de/api/joke',
            params=payload,
        )

        if answer.status_code is 200:
            await message.reply("Es gab Probleme beim Erreichen der API - kein Witz.")

            return

        answer = answer.content.decode('utf-8')
        data = json.loads(answer)

        await message.reply(data[0]['text'])

    # moves all users in the authors voice channel to the given one
    async def moveUsers(self, message: Message):
        channelName = message.content[6:]
        channels = self.discord.get_all_channels()
        author = message.author
        voiceChannels = []

        for channel in channels:
            if isinstance(channel, discord.VoiceChannel):
                voiceChannels.append(channel)

        channelDestination = None

        for channel in voiceChannels:
            if channel.name.lower() == channelName.lower():
                channelDestination = channel

                break

        if channelDestination is None:
            await message.reply("Der angegebene Channel existiert nicht!")

            # return

        authorId = message.author.id

        if not self.hasUserWantedRoles(author, RoleId.ADMIN, RoleId.MOD):
            await message.reply("Du hast keine Berechtigung für diesen Befehl!")

            return

        channelStart = None

        for channel in voiceChannels:
            for member in channel.members:
                if member.id == author.id:
                    channelStart = channel

                    break

            if channelStart:
                break

        if not channelStart:
            await message.reply("Du bist in keinem Voicechannel!")

            return

        if channelStart == channelDestination:
            await message.reply("Alle sind bereits in diesem Channel!")

            return

        membersInStartVc = channelStart.members

        try:
            for member in membersInStartVc:
                await member.move_to(channelDestination, reason="Command von " + str(author.id))
        except discord.Forbidden:
            await message.reply("Der Bot hat keine Rechte dies zutun!")

            return
        except discord.HTTPException:
            await message.reply("Something went wrong!")

            return

        await message.reply("Alle Mitglieder wurden verschoben!")
