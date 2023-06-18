from __future__ import annotations

from datetime import datetime, timedelta

from src.DiscordParameters.ExperienceParameter import ExperienceParameter
from src.Id.GuildId import GuildId
from src.InheritedCommands.Times import Time, OnlineTime, StreamTime, UniversityTime
from src.Helper import WriteSaveQuery
from src.Services import ExperienceService, QuotesManager, LogHelper
from src.Id.ChatCommand import ChatCommand
from src.Id.RoleId import RoleId
from src.Helper import ReadParameters as rp
from src.Helper.ReadParameters import Parameters as parameters
from discord import Message, Client, Member
from src.InheritedCommands.NameCounter import Counter, ReneCounter, FelixCounter, PaulCounter, BjarneCounter, \
    OlegCounter, JjCounter, CookieCounter, CarlCounter
from src.Repository.DiscordUserRepository import getDiscordUser

import string
import discord
import mysql.connector
import requests
import array
import json


def getMessageParts(content: string) -> array:
    messageParts = content.split(' ')
    return [part for part in messageParts if part.strip() != ""]


def getUserIdByTag(tag: string) -> int | None:  # TODO change in all usages
    try:
        return int(tag[2:len(tag) - 1])
    except ValueError:
        return None


def getTagStringFromId(tag: string) -> string:
    return "<@%s>" % tag


class ProcessUserInput:

    def __init__(self, client: Client):
        self.databaseConnection = mysql.connector.connect(
            user=rp.getParameter(parameters.USER),
            password=rp.getParameter(parameters.PASSWORD),
            host=rp.getParameter(parameters.HOST),
            database=rp.getParameter(parameters.NAME),
        )
        self.client = client
        self.logHelper = LogHelper.LogHelper(self.databaseConnection)

    async def processMessage(self, message: Message):
        if message.channel.guild.id is None or message.author.id is None:
            return

        dcUserDb = getDiscordUser(self.databaseConnection, message.author)

        if not dcUserDb:
            return

        # if message.channel.id != ChannelId.ChannelId.CHANNEL_BOT_TEST_ENVIRONMENT.value:
        if dcUserDb['message_count_all_time']:
            dcUserDb['message_count_all_time'] = dcUserDb['message_count_all_time'] + 1
        else:
            dcUserDb['message_count_all_time'] = 1
        es = ExperienceService.ExperienceService(self.databaseConnection, self.client)
        es.addExperience(dcUserDb, ExperienceParameter.XP_FOR_MESSAGE.value)

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
                "discord",
                userId,
                data
            )

            cursor.execute(query[0], query[1])
            self.databaseConnection.commit()

    async def processCommand(self, message: Message):
        command = message.content

        if not command.startswith('!'):
            qm = QuotesManager.QuotesManager(self.databaseConnection, self.client)
            await qm.checkForNewQuote(message)

            return

        command = self.getCommand(command)

        if ChatCommand.HELP == command:
            await self.sendHelp(message)
            self.logHelper.addLog(message)

        elif ChatCommand.WhatsApp == command:
            await self.manageWhatsAppSettings(message)
            self.logHelper.addLog(message)

        elif ChatCommand.LEADERBOARD == command:
            await self.sendLeaderboard(message)
            self.logHelper.addLog(message)

        elif ChatCommand.REGISTRATION == command:
            await self.sendRegistrationLink(message)
            self.logHelper.addLog(message)

        elif ChatCommand.LOGS == command:
            await self.sendLogs(message)
            self.logHelper.addLog(message)

        elif ChatCommand.XP_BOOST_SPIN == command:
            xpService = ExperienceService.ExperienceService(self.databaseConnection, self.client)
            await xpService.spinForXpBoost(message)
            self.logHelper.addLog(message)

        elif ChatCommand.XP_INVENTORY == command:
            xpService = ExperienceService.ExperienceService(self.databaseConnection, self.client)
            await xpService.handleXpInventory(message)
            self.logHelper.addLog(message)

        elif ChatCommand.XP == command:
            xpService = ExperienceService.ExperienceService(self.databaseConnection, self.client)
            await xpService.handleXpRequest(message)
            self.logHelper.addLog(message)

        # close the connection to the database at the end
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

    async def answerJoke(self, category: str):
        payload = {
            'language': 'de',
            'category': category,
        }

        answer = requests.get(
            'https://witzapi.de/api/joke',
            params=payload,
        )

        if answer.status_code != 200:
            return "Es gab Probleme beim Erreichen der API - kein Witz."

        answer = answer.content.decode('utf-8')
        data = json.loads(answer)

        return data[0]['text']

    # moves all users in the authors voice channel to the given one
    async def moveUsers(self, channelName: string, member: Member) -> string:
        channelDestination = None

        channels = self.client.get_all_channels()
        voiceChannels = []

        for channel in channels:
            if isinstance(channel, discord.VoiceChannel):
                voiceChannels.append(channel)

        for channel in voiceChannels:
            if channel.name.lower() == channelName.lower():
                channelDestination = channel

                break

        if channelDestination is None:
            return "Channel konnte nicht gefunden werden!"

        authorId = member.id

        if not self.hasUserWantedRoles(member, RoleId.ADMIN, RoleId.MOD):
            return "Du hast dazu keine Berechtigung!"

        channelStart = None

        for channel in voiceChannels:
            for channelMember in channel.members:
                if channelMember.id == authorId:
                    channelStart = channel

                    break

            if channelStart:
                break

        if not channelStart:
            return "Du bist mit keinem Voicechannel verbunden!"

        if channelStart == channelDestination:
            return "Alle befinden sich bereits in diesem Channel!"

        membersInStartVc = channelStart.members

        try:
            for member in membersInStartVc:
                await member.move_to(channelDestination, reason="Command von " + str(authorId))

            return "Alle User wurden erfolgreich verschoben!"
        except discord.Forbidden:
            return "Ich habe dazu leider keine Berechtigung!"
        except discord.HTTPException:
            return "Irgendetwas ist schief gelaufen!"

    async def accessTimeAndEdit(self, time: Time, userTag: string, member: Member, param: string | None) -> string:
        tag = getUserIdByTag(userTag)
        dcUserDb = self.getDiscordUserFromDatabase(tag)

        # TODO increase all

        if not dcUserDb or not time.getTime(dcUserDb) or time.getTime(dcUserDb) == 0:
            return "Dieser Benutzer war noch nie online!"

        if param and self.hasUserWantedRoles(member, RoleId.ADMIN, RoleId.MOD):
            try:
                correction = int(param)
            except ValueError:
                return "Deine Korrektur war keine Zahl!"

            onlineBefore = time.getTime(dcUserDb)

            time.increaseTime(dcUserDb, correction)

            onlineAfter = time.getTime(dcUserDb)
            self.saveDiscordUserToDatabase(dcUserDb['id'], dcUserDb)

            return "Die %s-Zeit von <@%s> wurde von %s Minuten auf %s Minuten korrigiert!" % (
                time.getName(), dcUserDb['user_id'], onlineBefore, onlineAfter
            )
        else:
            return time.getStringForTime(dcUserDb)

    async def sendHelp(self, message: Message):
        messageParts = getMessageParts(message.content)

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
        messageParts = getMessageParts(message.content)

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
        # messageParts = getMessageParts(message.content)

        # if len(messageParts) > 1 and messageParts[1] == 'xp':
        # TODO
        # return

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

        # await message.reply(answer)
        return answer

    def leaderboardHelperCounter(self, users, counter: Counter) -> string:
        if len(users) < 1:
            return ""

        answer = "\n- __%s-Counter__:\n" % counter.getNameOfCounter()

        for index, user in enumerate(users):
            answer += "\t%d: %s - %d\n" % (index + 1, user[0], user[1])

        return answer

    async def sendRegistrationLink(self, message: Message):
        link = "https://axellotl.de/register/"
        link += str(message.author.id)

        if not message.author.dm_channel:
            await message.author.create_dm()

            if not message.author.dm_channel:
                await message.reply("Es gab Probleme dir eine Nachricht zu schreiben!")

                return

        await message.reply("Dir wurde das Formular privat gesendet!")
        await message.author.dm_channel.send("Dein persönlicher Link zum registrieren: %s" % link)

    # TODO improve sending DMs
    async def accessNameCounterAndEdit(self, counter: Counter, userTag: str, member: Member, param: str) -> string:
        tag = getUserIdByTag(userTag)
        member = await self.client.get_guild(int(GuildId.GUILD_KVGG.value)).fetch_member(tag)
        dcUserDb = getDiscordUser(self.databaseConnection, member)

        if not dcUserDb:
            return "Dieser Benutzer existiert (noch) nicht!"

        counter.setDiscordUser(dcUserDb)

        if param and self.hasUserWantedRoles(member, RoleId.ADMIN, RoleId.MOD):
            try:
                value = int(param)
            except ValueError:
                return "Dein eingegebener Parameter war ungültig!"

            if int(dcUserDb['user_id']) == member.id and value < 0:
                return "Du darfst deinen eigenen Counter nicht verringern!"

            if counter.getCounterValue() + value < 0:
                counter.setCounterValue(0)
            else:
                counter.setCounterValue(counter.getCounterValue() + value)

                with self.databaseConnection.cursor() as cursor:
                    query, nones = WriteSaveQuery.writeSaveQuery(
                        'discord',
                        dcUserDb['id'],
                        dcUserDb
                    )

                    cursor.execute(query, nones)
                    self.databaseConnection.commit()

            return "Der %s-Counter von %s wurde um %d erhöht!" % (
                counter.getNameOfCounter(), getTagStringFromId(tag), value)
        else:
            with self.databaseConnection.cursor() as cursor:
                query, nones = WriteSaveQuery.writeSaveQuery(
                    'discord',
                    dcUserDb['id'],
                    dcUserDb
                )

                cursor.execute(query, nones)
                self.databaseConnection.commit()

            return "%s hat einen %s-Counter von %d!" % (
                getTagStringFromId(tag), counter.getNameOfCounter(), counter.getCounterValue())

        """
        # !NAME @Bjarne
        if messageLength == 2:
            await message.reply("%s hat einen %s-Counter von %d!" % (
                getTagStringFromId(tag), counter.getNameOfCounter(), counter.getCounterValue())
                                )

            return
        # !felix @Bjarne start / stop
        elif isinstance(counter, FelixCounter.FelixCounter) and messageParts[2] in FelixCounter.getAllKeywords():
            # !felix @Bjarne start
            if messageParts[2] == FelixCounter.FELIX_COUNTER_START_KEYWORD:
                # no timer set and not online -> can set timer
                if dcUserDb['channel_id'] is None and counter.getFelixTimer() is None:
                    date = None

                    # with time
                    if messageLength == 4:
                        # get the datetime
                        try:
                            timeToStart = datetime.strptime(messageParts[3], "%H:%M")
                            current = datetime.now()
                            timeToStart = timeToStart.replace(year=current.year, month=current.month, day=current.day)

                            # if the time is set to the next day
                            if timeToStart < datetime.now():
                                timeToStart = timeToStart + timedelta(days=1)

                            date = timeToStart
                        except ValueError:
                            try:
                                minutesFromNow = int(messageParts[3])
                            except ValueError:
                                await message.reply("Bitte gib eine gültige Zeit an! Zum Beispiel: '20' für 20 "
                                                    "Minuten oder '09:04' um den Timer um 09:04 Uhr zu starten!")

                                return

                            timeToStart = datetime.now() + timedelta(minutes=minutesFromNow)
                            date = timeToStart

                    if not date:
                        date = datetime.now()

                    link = FelixCounter.LIAR

                    if message.author.nick:
                        username = message.author.nick
                    else:
                        username = message.author.name

                    counter.setFelixTimer(date)
                    await message.reply("Der %s-Timer von %s wird um %s Uhr gestartet!" % (
                        counter.getNameOfCounter(), getTagStringFromId(tag), date.strftime("%H:%M"))
                                        )

                    authorId = message.author.id
                    author = await self.client.get_guild(int(GuildId.GUILD_KVGG.value)).fetch_member(authorId)

                    # TODO change to Felix-Counter receiver and not author
                    if not author.dm_channel:
                        await author.create_dm()

                        # check if dm_channel was really created
                        if not author.dm_channel:
                            return

                    await author.dm_channel.send("Dein %s-Timer wurde von %s auf %s Uhr gesetzt! Pro Minute "
                                                 "bekommst du ab dann einen %s-Counter dazu! Um den Timer zu "
                                                 "stoppen komm (vorher) online oder 'warte' ab dem Zeitpunkt 20 "
                                                 "Minuten!\n%s"
                                                 % (
                                                     counter.getNameOfCounter(),
                                                     username, date.strftime("%H:%M"),
                                                     counter.getNameOfCounter(),
                                                     link
                                                 ))
                # user online
                elif dcUserDb['channel_id'] is not None:
                    await message.reply("%s ist gerade online, du kannst für ihn / sie keinen %s-Timer starten!"
                                        % (getTagStringFromId(tag), counter.getNameOfCounter())
                                        )

                    return
                # timer already running
                elif counter.getFelixTimer() is not None:
                    await message.reply("Es läuft bereits ein Timer!")

                    return
                # if everything goes downhill
                else:
                    await message.reply("Es ist ein Fehler aufgetreten!")

                    return
            # !felix @Bjarne stop
            elif messageParts[2] == FelixCounter.FELIX_COUNTER_STOP_KEYWORD:
                if counter.getFelixTimer() is not None:
                    counter.setFelixTimer(None)
                    await message.reply("Der %s-Timer von %s wurde beendet!"
                                        % (counter.getNameOfCounter(), getTagStringFromId(tag)))

                    if message.author.nick:
                        username = message.author.nick
                    else:
                        username = message.author.name

                    authorId = message.author.id
                    author = await self.client.get_guild(int(GuildId.GUILD_KVGG.value)).fetch_member(authorId)

                    if not author.dm_channel:
                        await author.create_dm()

                        # check if dm_channel was really created
                        if not author.dm_channel:
                            return

                    # TODO send to receiver and not author
                    await author.dm_channel.send("Dein %s-Timer wurde von %s beendet!"
                                                 % (counter.getNameOfCounter(), username))

                else:
                    await message.reply("Es lief kein %s-Timer für %s!"
                                        % (counter.getNameOfCounter(), getTagStringFromId(tag)))
        elif self.hasUserWantedRoles(message.author, RoleId.ADMIN, RoleId.MOD):
            try:
                value = int(messageParts[2])
            except ValueError:
                await message.reply("Deine Eingabe war ungültig!")

                return

            if str(message.author.id) == dcUserDb['user_id'] and value < 0:
                await message.reply("Du darfst deinen eigenen %s-Counter nicht verringern!"
                                    % counter.getNameOfCounter())

                return

            if counter.getCounterValue() + value < 0:
                counter.setCounterValue(0)
            else:
                counter.setCounterValue(counter.getCounterValue() + value)
            await message.reply("Der %s-Counter von %s wurde um %d erhöht!"
                                % (counter.getNameOfCounter(), getTagStringFromId(tag), value))

        else:
            # check if entered value was a number
            try:
                value = int(messageParts[2])
            except ValueError:
                await message.reply("Deine Eingabe war falsch!")

                return

            counter.setCounterValue(counter.getCounterValue() + 1)
            await message.reply("Der %s-Counter von %s wurde um 1 erhöht!"
                                % (counter.getNameOfCounter(), getTagStringFromId(tag)))  #

        with self.databaseConnection.cursor() as cursor:
            query, nones = WriteSaveQuery.writeSaveQuery(
                'discord',
                dcUserDb['id'],
                dcUserDb
            )

            cursor.execute(query, nones)
            self.databaseConnection.commit()
        """

    async def sendLogs(self, member: Member, amount: int):
        if self.hasUserWantedRoles(member, RoleId.ADMIN, RoleId.MOD):
            with self.databaseConnection.cursor() as cursor:
                query = "SELECT discord.user_id, logs.command, logs.created_at " \
                        "FROM logs " \
                        "INNER JOIN discord " \
                        "WHERE discord_user_id = discord.id " \
                        "LIMIT %s"

                cursor.execute(query, (amount,))

                logs = cursor.fetchall()

                if not logs:
                    return "Es ist ein Fehler aufgetreten!"

            answer = "Die letzten %d Logs:\n\n" % amount

            for index, log in enumerate(logs):
                date: datetime = log[2]
                command = log[1]
                user = log[0]

                answer += "%d. \"**%s**\" von %s am %s\n" % (
                    index, command, getTagStringFromId(user), date.strftime("%Y-%m-%d %H:%M:%S"))

            return answer

        else:
            return "Du darfst diese Aktion nicht ausführen!"
