from __future__ import annotations
from src.InheritedCommands.Times import Time, OnlineTime, StreamTime
from src.Helper import WriteSaveQuery
from src.Id.ChatCommand import ChatCommand
from src.Id.RoleId import RoleId
from src.Helper import ReadParameters as rp
from src.Helper.ReadParameters import Parameters as parameters
from discord import Message, Client
from src.InheritedCommands.NameCounter import Counter, ReneCounter, FelixCounter, PaulCounter, BjarneCounter, OlegCounter, JjCounter, CookieCounter, CarlCounter

import string
import discord
import mysql.connector
import requests
import array
import json


class ProcessUserInput:

    def __init__(self, client: Client):
        self.databaseConnection = mysql.connector.connect(
            user=rp.getParameter(parameters.USER),
            password=rp.getParameter(parameters.PASSWORD),
            host=rp.getParameter(parameters.HOST),
            database=rp.getParameter(parameters.NAME),
        )
        self.client = client

    async def processMessage(self, message: Message):
        if message.channel.guild.id is None or message.author.id is None:
            return

        dcUserDb = self.getDiscordUserFromDatabase(message.author.id)

        if not dcUserDb:
            # TODO create
            return

        # if message.channel.id != ChannelId.ChannelId.CHANNEL_BOT_TEST_ENVIRONMENT.value:
        # TODO addExperience

        self.saveDiscordUserToDatabase(dcUserDb['id'], dcUserDb)

        await self.processCommand(message)

    def getDiscordUserFromDatabase(self, userId: int) -> dict | None:
        with self.databaseConnection.cursor() as cursor:
            query = "SELECT * FROM discord WHERE user_id = %s"

            cursor.execute(query, ([userId]))
            dcUserDb = cursor.fetchall()  # fetchone TODO

            if not dcUserDb:
                pass  # TODO create DiscordUser
                return None

            return dict(zip(cursor.column_names, dcUserDb[0]))

    def saveDiscordUserToDatabase(self, userId: string, data):
        with self.databaseConnection.cursor() as cursor:
            query = WriteSaveQuery.writeSaveQuery(
                rp.getParameter(rp.Parameters.NAME) + ".discord",
                userId,
                data
            )

            cursor.execute(query[0], query[1])
            self.databaseConnection.commit()

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
        elif ChatCommand.QUOTE == command:
            # TODO quotesManager.answerQuote()
            pass
        elif ChatCommand.TIME == command:
            await self.accessTimeAndEdit(OnlineTime.OnlineTime(), message)
        elif ChatCommand.HELP == command:
            await self.sendHelp(message)
        elif ChatCommand.STREAM == command:
            await self.accessTimeAndEdit(StreamTime.StreamTime(), message)
        elif ChatCommand.WhatsApp == command:
            await self.manageWhatsAppSettings(message)
        elif ChatCommand.LEADERBOARD == command:
            await self.sendLeaderboard(message)

        self.databaseConnection.close()

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

        if answer.status_code != 200:
            await message.reply("Es gab Probleme beim Erreichen der API - kein Witz.")

            return

        answer = answer.content.decode('utf-8')
        data = json.loads(answer)

        await message.reply(data[0]['text'])

    # moves all users in the authors voice channel to the given one
    async def moveUsers(self, message: Message):
        channelName = message.content[6:]
        channels = self.client.get_all_channels()
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

    def getMessageparts(self, message: string) -> array:
        messageParts = message.split(' ')
        return [part for part in messageParts if part.strip() != ""]

    def getUserIdByTag(self, tag: string) -> string:
        return tag[2:len(tag) - 1]

    async def accessTimeAndEdit(self, time: Time, message: Message):
        messageParts = self.getMessageparts(message.content)

        if len(messageParts) == 1:
            dcUserDb = self.getDiscordUserFromDatabase(message.author.id)

            if not dcUserDb:
                await message.reply("Du warst noch nie online!")

                return

            await message.reply(time.getStringForTime(dcUserDb))

            return

        tag = self.getUserIdByTag(messageParts[1])
        dcUserDb = self.getDiscordUserFromDatabase(tag)

        # TODO all

        if not dcUserDb or not time.getTime(dcUserDb) or time.getTime(dcUserDb) == 0:
            await message.reply("Dieser Benutzer war noch nie online!")

            return

        if len(messageParts) > 2 and self.hasUserWantedRoles(message.author, RoleId.ADMIN, RoleId.MOD):
            try:
                correction = int(messageParts[2])
            except ValueError:
                await message.reply("Deine Korrektur war keine Zahl!")

                return

            onlineBefore = time.getTime(dcUserDb)

            time.increaseTime(dcUserDb, correction)

            onlineAfter = time.getTime(dcUserDb)
            self.saveDiscordUserToDatabase(dcUserDb['id'], dcUserDb)

            await message.reply(
                "Die %s-Zeit von <@%s> wurde von %s Minuten auf %s Minuten korrigiert!" %
                (time.getName(), dcUserDb['user_id'], onlineBefore, onlineAfter),
            )
        elif len(messageParts) > 2:
            await message.reply("Du darfst nur die Zeit anfragen!")
        else:
            await message.reply(time.getStringForTime(dcUserDb))

    async def sendHelp(self, message: Message):
        messageParts = self.getMessageparts(message.content)

        if len(messageParts) < 2:
            output = ""

            with self.databaseConnection.cursor() as cursor:
                for chatCommand in ChatCommand:
                    query = "SELECT command, explanation FROM commands WHERE command = %s"

                    cursor.execute(query, (chatCommand.value,))

                    command = cursor.fetchone()
                    cursor.reset()

                    output += "**__" + str(command[0]) + "__**: " + str(command[1]) + "\n\n"

            await message.reply(output)

        elif len(messageParts) == 2:
            command = self.getCommand(messageParts[1])

            if not command:
                await message.reply("Diesen Befehl gibt es nicht!")

                return
            elif command == ChatCommand.XP:
                pass  # TODO
                return

            query = "SELECT execute_explanation FROM commands WHERE command = %s"

            with self.databaseConnection.cursor() as cursor:
                cursor.execute(query, (command.value,))

                commandExplanation = cursor.fetchone()

            if not commandExplanation[0]:
                await message.reply("Schreib einfach '%s', mehr gibt es nicht!" % command.value)
            else:
                await message.reply("'%s'" % commandExplanation[0])

    async def manageWhatsAppSettings(self, message: Message):
        messageParts = self.getMessageparts(message.content)

        # get dcUserDb with user
        with self.databaseConnection.cursor() as cursor:
            query = "SELECT u.id, recieve_join_notification, receive_leave_notification, " \
                    "receive_uni_join_notification, receive_uni_leave_notification " \
                    "FROM discord INNER JOIN user u " \
                    "ON discord.id = u.discord_user_id " \
                    "WHERE discord.user_id = %s"

            cursor.execute(query, (message.author.id,))
            user = dict(zip(cursor.column_names, list(cursor.fetchone())))

        if not user:
            await message.reply("Es ist ein Fehler aufgetreten!")

            return
        elif len(messageParts) < 2:
            await message.reply("Zu wenige Argumente!")

            return

        # !whatsapp join
        if messageParts[1] == 'join':
            # !whatsapp join []
            if len(messageParts) < 3:
                await message.reply("Fehlendes Argument nach '%s'!" % messageParts[1])

                return

            # !whatsapp join on
            if messageParts[2] == 'on':
                user['recieve_join_notification'] = 1

            # !whatsapp join off
            elif messageParts[2] == 'off':
                user['recieve_join_notification'] = 0

            # !whatsapp join aisugd
            else:
                await message.reply("Falsches Argument nach '%s'!" % messageParts[1])

                return

        # !whatsapp leave
        elif messageParts[1] == 'leave':
            # !whatsapp leave []
            if len(messageParts) < 3:
                await message.reply("Fehlendes Argument nach '%s'!" % messageParts[1])

                return

            # !whatsapp leave on
            if messageParts[2] == 'on':
                user['receive_leave_notification'] = 1

            # !whatsapp leave off
            elif messageParts[2] == 'off':
                user['receive_leave_notification'] = 0

            # !whatsapp leave aisugd
            else:
                await message.reply("Falsches Argument nach '%s'!" % messageParts[1])

                return

        # !whatsapp uni
        elif messageParts[1] == 'uni':
            if len(messageParts) == 2:
                await message.reply("Fehlendes Argument nach '%s'!" % messageParts[1])

                return

            if messageParts[2] == 'join':
                if len(messageParts) == 3:
                    await message.reply("Fehlendes Argument nach '%s'!" % messageParts[2])

                    return

                if messageParts[3] == 'on':
                    user['receive_uni_join_notification'] = 1
                elif messageParts[3] == 'off':
                    user['receive_uni_join_notification'] = 0
                else:
                    await message.reply("Falsches Argument nach '%s'!" % messageParts[2])

            elif messageParts[2] == 'leave':
                if len(messageParts) == 3:
                    await message.reply("Fehlendes Argument nach '%s'!" % messageParts[2])

                    return

                if messageParts[3] == 'on':
                    user['receive_uni_leave_notification'] = 1
                elif messageParts[3] == 'off':
                    user['receive_uni_leave_notification'] = 0
                else:
                    await message.reply("Falsches Argument nach '%s'!" % messageParts[2])

            else:
                await message.reply("Dies ist keine Möglichkeit!")

                return

        else:
            await message.reply("Dies ist keine Möglichkeit!")

            return

        with self.databaseConnection.cursor() as cursor:
            query, noneTuple = WriteSaveQuery.writeSaveQuery(
                rp.getParameter(rp.Parameters.NAME) + ".user",
                user['id'],
                user
            )

            cursor.execute(query, noneTuple)
            self.databaseConnection.commit()

        await message.reply("Deine Einstellung wurde übernommen!")

    async def sendLeaderboard(self, message: Message):
        messageParts = self.getMessageparts(message.content)

        if len(messageParts) > 1 and messageParts[1] == 'xp':
            # TODO
            return

        with self.databaseConnection.cursor() as cursor:
            # online time
            query = "SELECT username, formated_time " \
                    "FROM discord " \
                    "WHERE time_online IS NOT NULL " \
                    "ORDER BY time_online DESC " \
                    "LIMIT 3"

            cursor.execute(query)
            usersOnlineTime = cursor.fetchall()
            cursor.reset()

            # stream time
            query = "SELECT username, formatted_stream_time " \
                    "FROM discord " \
                    "WHERE time_streamed IS NOT NULL " \
                    "ORDER BY time_streamed DESC " \
                    "LIMIT 3"

            cursor.execute(query)
            usersStreamTime = cursor.fetchall()
            cursor.reset()

            # message count
            query = "SELECT username, message_count_all_time " \
                    "FROM discord " \
                    "WHERE message_count_all_time != 0 " \
                    "ORDER BY message_count_all_time DESC " \
                    "LIMIT 3"

            cursor.execute(query)
            usersMessageCount = cursor.fetchall()
            cursor.reset()

            # Rene counter
            query = "SELECT username, rene_counter " \
                    "FROM discord " \
                    "WHERE rene_counter != 0 " \
                    "ORDER BY rene_counter DESC " \
                    "LIMIT 3"

            cursor.execute(query)
            usersReneCounter = cursor.fetchall()
            cursor.reset()

            # Felix counter
            query = "SELECT username, felix_counter " \
                    "FROM discord " \
                    "WHERE felix_counter != 0 " \
                    "ORDER BY felix_counter DESC " \
                    "LIMIT 3"

            cursor.execute(query)
            usersFelixCounter = cursor.fetchall()
            cursor.reset()

            # Paul counter
            query = "SELECT username, paul_counter " \
                    "FROM discord " \
                    "WHERE paul_counter != 0 " \
                    "ORDER BY paul_counter DESC " \
                    "LIMIT 3"

            cursor.execute(query)
            usersPaulCounter = cursor.fetchall()
            cursor.reset()

            # Bjarne counter
            query = "SELECT username, bjarne_counter " \
                    "FROM discord " \
                    "WHERE bjarne_counter != 0 " \
                    "ORDER BY bjarne_counter DESC " \
                    "LIMIT 3"

            cursor.execute(query)
            usersBjarneCounter = cursor.fetchall()
            cursor.reset()

            # JJ counter
            query = "SELECT username, jj_counter " \
                    "FROM discord " \
                    "WHERE jj_counter != 0 " \
                    "ORDER BY jj_counter DESC " \
                    "LIMIT 3"

            cursor.execute(query)
            usersJjCounter = cursor.fetchall()
            cursor.reset()

            # Oleg counter
            query = "SELECT username, oleg_counter " \
                    "FROM discord " \
                    "WHERE oleg_counter != 0 " \
                    "ORDER BY oleg_counter DESC " \
                    "LIMIT 3"

            cursor.execute(query)
            usersOlegCounter = cursor.fetchall()
            cursor.reset()

            # Carl counter
            query = "SELECT username, carl_counter " \
                    "FROM discord " \
                    "WHERE carl_counter != 0 " \
                    "ORDER BY carl_counter DESC " \
                    "LIMIT 3"

            cursor.execute(query)
            usersCarlCounter = cursor.fetchall()
            cursor.reset()

            # Cookie counter
            query = "SELECT username, cookie_counter " \
                    "FROM discord " \
                    "WHERE cookie_counter != 0 " \
                    "ORDER BY cookie_counter DESC " \
                    "LIMIT 3"

            cursor.execute(query)
            usersCookieCounter = cursor.fetchall()

        answer = "--------------\n"
        answer += "__**Leaderboard**__\n"
        answer += "--------------\n\n"
        answer += "- __Online-Zeit__:\n"

        if len(usersOnlineTime) != 0:
            for index, user in enumerate(usersOnlineTime):
                answer += "\t%d: %s - %s\n" % (index + 1, user[0], user[1])

        answer += "\n- __Stream-Zeit__:\n"

        if len(usersStreamTime) != 0:
            for index, user in enumerate(usersStreamTime):
                answer += "\t%d: %s - %s\n" % (index + 1, user[0], user[1])

        answer += "\n- __Anzahl an gesendeten Nachrichten__:\n"

        if len(usersMessageCount) != 0:
            for index, user in enumerate(usersMessageCount):
                answer += "\t%d: %s - %s\n" % (index + 1, user[0], user[1])

        answer += self.leaderboardHelperCounter(usersReneCounter, ReneCounter.ReneCounter())
        answer += self.leaderboardHelperCounter(usersFelixCounter, FelixCounter.FelixCounter())
        answer += self.leaderboardHelperCounter(usersPaulCounter, PaulCounter.PaulCounter())
        answer += self.leaderboardHelperCounter(usersBjarneCounter, BjarneCounter.BjarneCounter())
        answer += self.leaderboardHelperCounter(usersOlegCounter, OlegCounter.OlegCounter())
        answer += self.leaderboardHelperCounter(usersJjCounter, JjCounter.JjCounter())
        answer += self.leaderboardHelperCounter(usersCookieCounter, CookieCounter.CookieCounter())
        answer += self.leaderboardHelperCounter(usersCarlCounter, CarlCounter.CarlCounter())

        await message.reply(answer)

    def leaderboardHelperCounter(self, users, counter: Counter) -> string:
        if len(users) < 1:
            return ""

        answer = "\n- __%s-Counter__:\n" % counter.getNameOfCounter()

        for index, user in enumerate(users):
            answer += "\t%d: %s - %d\n" % (index + 1, user[0], user[1])

        return answer
