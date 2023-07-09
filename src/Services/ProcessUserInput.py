from __future__ import annotations

import array
import asyncio
import json
import logging
import os
import string
from datetime import datetime, timedelta

import discord
import requests
from discord import Message, Client, Member

from src.DiscordParameters.ExperienceParameter import ExperienceParameter
from src.Helper import ReadParameters as rp
from src.Helper import WriteSaveQuery
from src.Helper.CreateNewDatabaseConnection import getDatabaseConnection
from src.Helper.getFormattedTime import getFormattedTime
from src.Id import ChannelId
from src.Id.ChannelIdUniversityTracking import ChannelIdUniversityTracking
from src.Id.ChannelIdWhatsAppAndTracking import ChannelIdWhatsAppAndTracking
from src.Id.ChatCommand import ChatCommand
from src.Id.GuildId import GuildId
from src.Id.RoleId import RoleId
from src.InheritedCommands.NameCounter import Counter, ReneCounter, FelixCounter, PaulCounter, BjarneCounter, \
    OlegCounter, JjCounter, CookieCounter, CarlCounter
from src.InheritedCommands.Times import Time
from src.Repository.DiscordUserRepository import getDiscordUser, getOnlineUsers, getDiscordUserById
from src.Services import ExperienceService, QuotesManager, LogHelper

logger = logging.getLogger("KVGG_BOT")
SECRET_KEY = os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False)


def getMessageParts(content: string) -> array:
    """
    Splits the string at spaces, removes empty splits

    :param content: String to split
    :return:
    """
    messageParts = content.split(' ')
    return [part for part in messageParts if part.strip() != ""]


def getUserIdByTag(tag: string) -> int | None:
    """
    Filters out the user id from a tag <@123> => 123

    :param tag: tag from Discord
    :return: int - user id
    """
    try:
        return int(tag[2:len(tag) - 1])
    except ValueError:
        return None


def getTagStringFromId(tag: string) -> string:
    """
    Builds a tag from the given user id 123 => <@123>

    :param tag: Tag to be transformed
    :return:
    """
    return "<@%s>" % tag


def hasUserWantedRoles(author: Message.author, *roles) -> bool:
    """
    Compares the wanted roles with the ones the author has

    :param author: Member, whose roles are checked
    :param roles: Roles to be allowed
    :return:
    """
    for role in roles:
        id = role.value
        rolesFromAuthor = author.roles

        for roleAuthor in rolesFromAuthor:
            if id == roleAuthor.id:
                return True

    return False


class ProcessUserInput:
    """
    Handles almost all things regarding the chat and commands
    """

    def __init__(self, client: Client):
        self.databaseConnection = getDatabaseConnection()
        self.client = client
        self.logHelper = LogHelper.LogHelper()

    def processMessage(self, message: Message):
        """
        Increases the message count and adds XP

        :param message:
        :return:
        """
        logger.info("%s initated the processing of his / her message" % message.author.name)

        if message.channel.guild.id is None or message.author.id is None:
            logger.warning("GuildId or AuthorId were None")

            return

        dcUserDb = getDiscordUser(self.databaseConnection, message.author)

        if not dcUserDb:
            logger.warning("Couldn't fetch DiscordUser!")

            return

        if message.channel.id != int(ChannelId.ChannelId.CHANNEL_BOT_TEST_ENVIRONMENT.value):
            if dcUserDb['message_count_all_time']:
                dcUserDb['message_count_all_time'] = dcUserDb['message_count_all_time'] + 1
            else:
                dcUserDb['message_count_all_time'] = 1
        elif not SECRET_KEY:
            logger.info("Overwrite message count")

            if dcUserDb['message_count_all_time']:
                dcUserDb['message_count_all_time'] = dcUserDb['message_count_all_time'] + 1
            else:
                dcUserDb['message_count_all_time'] = 1

        es = ExperienceService.ExperienceService(self.client)
        es.addExperience(ExperienceParameter.XP_FOR_MESSAGE.value, dcUserDb)

        self.__saveDiscordUserToDatabase(dcUserDb['id'], dcUserDb)

    def raiseMessageCounter(self, member: Member, channel):
        """
        Increases the message count if the given user if he / she used an interaction

        :param member: Member, who called the interaction
        :param channel: Channel, where the interaction was used
        :return:
        """
        logger.info("Increasing message-count for %s" % member.name)

        dcUserDb = getDiscordUser(self.databaseConnection, member)

        if dcUserDb is None:
            logger.warning("Couldn't fetch DiscordUser!")

        if channel.id != ChannelId.ChannelId.CHANNEL_BOT_TEST_ENVIRONMENT.value and SECRET_KEY:
            if dcUserDb['message_count_all_time']:
                dcUserDb['message_count_all_time'] = dcUserDb['message_count_all_time'] + 1
            else:
                dcUserDb['message_count_all_time'] = 1

        self.__saveDiscordUserToDatabase(dcUserDb['id'], dcUserDb)

    @DeprecationWarning
    def __getDiscordUserFromDatabase(self, userId: int) -> dict | None:
        with self.databaseConnection.cursor() as cursor:
            query = "SELECT * FROM discord WHERE user_id = %s"

            cursor.execute(query, ([userId]))
            dcUserDb = cursor.fetchall()

            if not dcUserDb:
                pass
                return None

            return dict(zip(cursor.column_names, dcUserDb[0]))

    def __saveDiscordUserToDatabase(self, primaryKey: string, data):
        """
        Helper to save a DiscordUser from this class into the database

        :param primaryKey: Primary key of the user
        :param data: Data
        :return:
        """
        with self.databaseConnection.cursor() as cursor:
            query, nones = WriteSaveQuery.writeSaveQuery(
                "discord",
                primaryKey,
                data
            )

            cursor.execute(query, nones)
            self.databaseConnection.commit()

    @DeprecationWarning
    async def __processCommand(self, message: Message):
        """
        :param message:
        :return:
        """
        command = message.content

        if not command.startswith('!'):
            qm = QuotesManager.QuotesManager(self.client)
            await qm.checkForNewQuote(message)

            return

        command = self.__getCommand(command)

        # close the connection to the database at the end
        self.databaseConnection.close()

    @DeprecationWarning
    def __getCommand(self, command: string) -> ChatCommand | None:
        command = command.split(' ')[0]

        for enum_command in ChatCommand:
            if enum_command.value == command:
                return enum_command

        return None

    async def answerJoke(self, member: Member, category: str):
        """
        Answers a joke from an API

        :param category: Optional category of the joke - might not work due to API limitations
        :return:
        """
        logger.info("%s requested a joke" % member.name)

        payload = {
            'language': 'de',
            'category': category,
        }

        answer = requests.get(
            'https://witzapi.de/api/joke',
            params=payload,
        )

        if answer.status_code != 200:
            logger.warning("API sent an invalid response!")

            return "Es gab Probleme beim Erreichen der API - kein Witz."

        answer = answer.content.decode('utf-8')
        data = json.loads(answer)

        return data[0]['text']

    async def moveUsers(self, channelName: string, member: Member) -> string:
        """
        Moves all users from the initiator channel to the given one

        :param channelName: Chosen channel to move user to
        :param member: Member who initiated the move
        :return:
        """
        logger.info("%s requested to move users into %s" % (member.name, channelName))

        channelStart = member.voice.channel

        if not channelStart:
            return "Du bist mit keinem Voicechannel verbunden!"
        elif str(channelStart.id) not in ChannelIdWhatsAppAndTracking.getValues():
            return "Dein Channel befindet sich außerhalb des erlaubten Channel-Spektrums!"

        channelDestination = None
        channels = self.client.get_all_channels()

        for channel in channels:
            if isinstance(channel, discord.VoiceChannel):
                if channel.name.lower() == channelName.lower():
                    channelDestination = channel

                    break

        if channelDestination is None:
            logger.warning("Couldn't fetch channel!")

            return "Channel konnte nicht gefunden werden!"

        if channelStart.id == channelDestination.id:
            return "Alle befinden sich bereits in diesem Channel!"

        if str(channelDestination.id) not in ChannelIdWhatsAppAndTracking.getValues():
            return "Dieser Channel befindet sich außerhalb des erlaubten Channel-Spektrums!"

        canProceed = False

        for role in member.roles:
            permissions = channelDestination.permissions_for(role)
            if permissions.view_channel and permissions.connect:
                canProceed = True

                break

        if not canProceed:
            return "Du hast keine Berechtigung in diesen Channel zu moven!"

        membersInStartVc = channelStart.members
        loop = asyncio.get_event_loop()

        async def asyncioGenerator():
            try:
                await asyncio.gather(*[member.move_to(channelDestination) for member in membersInStartVc])
            except discord.Forbidden:
                logger.error("I dont have rights move the users!")

                return "Ich habe dazu leider keine Berechtigung!"
            except discord.HTTPException as e:
                logger.warning("Something went wrong!", exc_info=e)

                return "Irgendetwas ist schief gelaufen!"

        try:
            loop.run_until_complete(asyncioGenerator())
        except Exception as e:
            logger.error("Somthing went wrong while using asyncio!")

            return "Irgendetwas ist schief gelaufen!"

        return "Alle User wurden erfolgreich verschoben!"

    async def accessTimeAndEdit(self, time: Time, userTag: string, member: Member, param: string | None) -> string:
        """
        Answering given Time from given User or adds (subtracts) given amount

        :param time: Time-type
        :param userTag: Requested user
        :param member: Requesting Member
        :param param: Optional amount of time added or subtracted
        :return:
        """
        logger.info("%s requested %s-Time" % (member.name, time.getName()))

        # all users
        if userTag == 'all' and param and hasUserWantedRoles(member, RoleId.ADMIN, RoleId.MOD):
            try:
                correction = int(param)
            except ValueError:
                return "Deine Korrektur war keine Zahl!"

            users = getOnlineUsers(self.databaseConnection)

            if users is None:
                return "Es ist keiner online der Zeit dazu bekommen könnte!"

            reply = ""

            for user in users:
                if user['channel_id'] in ChannelIdUniversityTracking.getValues():
                    user['university_time_online'] += correction
                    user['formated_university_time'] = getFormattedTime(user['university_time_online'])
                    reply += "Die Uni-Zeit von %s wurde um %d erhöht!\n" % (
                        getTagStringFromId(user['user_id']), correction)

                elif user['channel_id'] in ChannelIdWhatsAppAndTracking.getValues():
                    user['time_online'] += correction
                    user['formated_time'] = getFormattedTime(user['time_online'])
                    reply += "Die Online-Zeit von %s wurde um %d erhöht!\n" % (
                        getTagStringFromId(user['user_id']), correction)

                    if user['started_stream_at'] or user['started_webcam_at']:
                        user['time_streamed'] += correction
                        user['formatted_stream_time'] = getFormattedTime(user['time_streamed'])
                        reply += "Die Stream-Zeit von %s wurde um %d erhöht!\n" % (
                            getTagStringFromId(user['user_id']), correction)

                self.__saveDiscordUserToDatabase(user['id'], user)

            return reply

        if (tag := getUserIdByTag(userTag)) is None:
            return "Bitte tagge einen User korrekt!"

        dcUserDb = getDiscordUserById(self.databaseConnection, tag)

        if not dcUserDb or not time.getTime(dcUserDb) or time.getTime(dcUserDb) == 0:
            if not dcUserDb:
                logger.warning("Couldn't fetch DiscordUser!")

            return "Dieser Benutzer war noch nie online!"

        if param and hasUserWantedRoles(member, RoleId.ADMIN, RoleId.MOD):
            try:
                correction = int(param)
            except ValueError:
                return "Deine Korrektur war keine Zahl!"

            onlineBefore = time.getTime(dcUserDb)

            time.increaseTime(dcUserDb, correction)

            onlineAfter = time.getTime(dcUserDb)
            self.__saveDiscordUserToDatabase(dcUserDb['id'], dcUserDb)

            return "Die %s-Zeit von <@%s> wurde von %s Minuten auf %s Minuten korrigiert!" % (
                time.getName(), dcUserDb['user_id'], onlineBefore, onlineAfter
            )
        else:
            return time.getStringForTime(dcUserDb)

    @DeprecationWarning
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
            command = self.__getCommand(messageParts[1])

            if not command:
                await message.reply("Diesen Befehl gibt es nicht!")

                return
            elif command == ChatCommand.XP:
                pass
                return

            query = "SELECT execute_explanation FROM commands WHERE command = %s"

            with self.databaseConnection.cursor() as cursor:
                cursor.execute(query, (command.value,))

                commandExplanation = cursor.fetchone()

            if not commandExplanation[0]:
                await message.reply("Schreib einfach '%s', mehr gibt es nicht!" % command.value)
            else:
                await message.reply("'%s'" % commandExplanation[0])

    async def manageWhatsAppSettings(self, member: Member, type: str, action: str, switch: str):
        """
        Lets the user change their WhatsApp settings

        :param member: Member, who requested a change of his / her settings
        :param type: Type of messages (gaming or university)
        :param action: Action of the messages (join or leave)
        :param switch: Switch (on / off)
        :return:
        """
        logger.info("%s requested a change of his / her WhatsApp settings" % member.name)

        # get dcUserDb with user
        with self.databaseConnection.cursor() as cursor:
            query = "SELECT u.id, recieve_join_notification, receive_leave_notification, " \
                    "receive_uni_join_notification, receive_uni_leave_notification " \
                    "FROM discord INNER JOIN user u " \
                    "ON discord.id = u.discord_user_id " \
                    "WHERE discord.user_id = %s"

            cursor.execute(query, (member.id,))
            user = dict(zip(cursor.column_names, cursor.fetchone()))

        if not user:
            logger.warning("Couldn't fetch corresponding user!")

            return "Du bist nicht als User bei uns registriert!"

        if type == 'Gaming':
            # !whatsapp join
            if action == 'join':
                # !whatsapp join on
                if switch == 'on':
                    user['recieve_join_notification'] = 1

                # !whatsapp join off
                elif switch == 'off':
                    user['recieve_join_notification'] = 0

            # !whatsapp leave
            elif action == 'leave':
                # !whatsapp leave on
                if switch == 'on':
                    user['receive_leave_notification'] = 1

                # !whatsapp leave off
                elif switch == 'off':
                    user['receive_leave_notification'] = 0

        # !whatsapp uni
        elif type == 'Uni':
            if action == 'join':
                if switch == 'on':
                    user['receive_uni_join_notification'] = 1
                elif switch == 'off':
                    user['receive_uni_join_notification'] = 0

            elif action == 'leave':
                if switch == 'on':
                    user['receive_uni_leave_notification'] = 1
                elif switch == 'off':
                    user['receive_uni_leave_notification'] = 0

        with self.databaseConnection.cursor() as cursor:
            query, noneTuple = WriteSaveQuery.writeSaveQuery(
                rp.getParameter(rp.Parameters.NAME) + ".user",
                user['id'],
                user
            )

            cursor.execute(query, noneTuple)
            self.databaseConnection.commit()

        return "Deine Einstellung wurde übernommen!"

    async def sendLeaderboard(self, member: Member) -> string:
        """
        Returns the leaderboard of our stats in the database

        :param member: Member, who requested the leaderboard
        :return:
        """
        logger.info("%s requested our leaderboard" % member.name)

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

        answer += self.__leaderboardHelperCounter(usersReneCounter, ReneCounter.ReneCounter())
        answer += self.__leaderboardHelperCounter(usersFelixCounter, FelixCounter.FelixCounter())
        answer += self.__leaderboardHelperCounter(usersPaulCounter, PaulCounter.PaulCounter())
        answer += self.__leaderboardHelperCounter(usersBjarneCounter, BjarneCounter.BjarneCounter())
        answer += self.__leaderboardHelperCounter(usersOlegCounter, OlegCounter.OlegCounter())
        answer += self.__leaderboardHelperCounter(usersJjCounter, JjCounter.JjCounter())
        answer += self.__leaderboardHelperCounter(usersCookieCounter, CookieCounter.CookieCounter())
        answer += self.__leaderboardHelperCounter(usersCarlCounter, CarlCounter.CarlCounter())

        return answer

    def __leaderboardHelperCounter(self, users, counter: Counter) -> string:
        """
        Helper for listing a leaderboard entry for given counter

        :param users: List of users
        :param counter: counter-type
        :return:
        """
        if len(users) < 1:
            return ""

        answer = "\n- __%s-Counter__:\n" % counter.getNameOfCounter()

        for index, user in enumerate(users):
            answer += "\t%d: %s - %d\n" % (index + 1, user[0], user[1])

        return answer

    async def sendRegistrationLink(self, member: Member):
        """
        Sends an individual invitaion link to the member who requested it

        :param member:
        :return:
        """
        logger.info("%s request a registration link" % member.name)

        link = "https://axellotl.de/register/"
        link += str(member.id)

        if not member.dm_channel:
            await member.create_dm()

            if not member.dm_channel:
                logger.warning("Couldn't create DM for %s!" % member.name)

                return "Es gab Probleme dir eine Nachricht zu schreiben!"

        await member.dm_channel.send("Dein persönlicher Link zum registrieren: %s" % link)

        return "Dir wurde das Formular privat gesendet!"

    async def accessNameCounterAndEdit(self, counter: Counter, userTag: str, member: Member, param: str) -> string:
        """
        Answering given Counter from given User or adds (subtracts) given amount

        :param counter: Chosen counter-type
        :param userTag: User which counter was requested
        :param member: Member who requested the counter
        :param param: Optional amount of time to add / subtract
        :return:
        """
        logger.info("%s requested %s-Counter" % (member.name, counter.getNameOfCounter()))

        if (tag := getUserIdByTag(userTag)) is None:
            return "Bitte tagge einen User korrekt!"

        # get requested user as member from guild
        try:
            memberCounter = await self.client.get_guild(int(GuildId.GUILD_KVGG.value)).fetch_member(tag)
        except discord.errors.HTTPException:
            logger.warning("Couldn't fetch member from guild!")

            return "Entweder existiert der Nutzer / die Nutzerin nicht oder es gab einen Fehler!"

        dcUserDb = getDiscordUser(self.databaseConnection, memberCounter)

        if not dcUserDb:
            logger.warning("Couldn't fetch DiscordUser!")

            return "Dieser Benutzer existiert (noch) nicht!"

        counter.setDiscordUser(dcUserDb)

        if param and hasUserWantedRoles(member, RoleId.ADMIN, RoleId.MOD):
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

    async def handleFelixTimer(self, member: Member, tag: string, action: string, zeit: string = None):
        """
        Handles the Feli-Timer for the given user

        :param member: Member, who raised the command
        :param tag: Tag of the user whose timer will be edited
        :param action: Chosen action, start or stop
        :param zeit: Optional time to start the timer at
        :return:
        """
        logger.info("Handling Felix-Timer by %s" % member.name)

        userId = getUserIdByTag(tag)
        dcUserDb = getDiscordUserById(self.databaseConnection, userId)

        if not dcUserDb:
            logger.warning("Couldn't fetch DiscordUser!")

            return "Bitte tagge deinen User korrekt!"

        counter = FelixCounter.FelixCounter(dcUserDb)

        if action == "start":
            if dcUserDb['channel_id'] is None and counter.getFelixTimer() is None:
                date = None

                if not zeit:
                    return "Bitte gib eine Zeit an!"

                try:
                    timeToStart = datetime.strptime(zeit, "%H:%M")
                    current = datetime.now()
                    timeToStart = timeToStart.replace(year=current.year, month=current.month, day=current.day)

                    # if the time is set to the next day
                    if timeToStart < datetime.now():
                        timeToStart = timeToStart + timedelta(days=1)

                    date = timeToStart
                except ValueError:
                    try:
                        minutesFromNow = int(zeit)
                    except ValueError:
                        return "Bitte gib eine gültige Zeit an! Zum Beispiel: '20' für 20 Minuten oder '09:04' um den " \
                               "Timer um 09:04 Uhr zu starten!"

                    timeToStart = datetime.now() + timedelta(minutes=minutesFromNow)
                    date = timeToStart

                if not date:
                    return "Deine gegebene Zeit war inkorrekt. Bitte achte auf das Format: '09:09' oder '20'!"

                link = FelixCounter.LIAR

                if member.nick:
                    username = member.nick
                else:
                    username = member.name

                counter.setFelixTimer(date)
                self.__saveDiscordUserToDatabase(dcUserDb['id'], dcUserDb)

                answer = "Der %s-Timer von %s wird um %s Uhr gestartet!" % (
                    counter.getNameOfCounter(), tag, date.strftime("%H:%M"))

                memberDm = self.client.get_guild(int(GuildId.GUILD_KVGG.value)).get_member(userId)

                if not memberDm:
                    logger.warning("Couldn't fetch member from Guild!")

                    return

                if not memberDm.dm_channel:
                    await memberDm.create_dm()

                    if not memberDm.dm_channel:
                        logger.warning("Couldn't create DM-Channel with %s!" % memberDm.name)

                        return answer

                await memberDm.dm_channel.send("Dein %s-Timer wurde von %s auf %s Uhr gesetzt! Pro Minute "
                                               "bekommst du ab dann einen %s-Counter dazu! Um den Timer zu "
                                               "stoppen komm (vorher) online oder 'warte' ab dem Zeitpunkt 20 "
                                               "Minuten!\n"
                                               % (
                                                   counter.getNameOfCounter(),
                                                   username, date.strftime("%H:%M"),
                                                   counter.getNameOfCounter(),
                                               ))
                await memberDm.dm_channel.send(link)

                return answer

            elif dcUserDb['channel_id'] is not None:
                return "%s ist gerade online, du kannst für ihn / sie keinen %s-Timer starten!" % (
                    tag, counter.getNameOfCounter())

            elif counter.getFelixTimer() is not None:
                return "Es läuft bereits ein Timer!"

            else:
                logger.error("No matching condition were found for starting a Felix-Timer!")

                return "Es ist ein Fehler aufgetreten!"

        elif action == "stop":
            if counter.getFelixTimer() is not None:
                counter.setFelixTimer(None)

                if member.nick:
                    username = member.nick
                else:
                    username = member.name

                answer = "Der %s-Timer von %s wurde beendet!" % (counter.getNameOfCounter(), tag)

                self.__saveDiscordUserToDatabase(dcUserDb['id'], dcUserDb)

                memberDm = self.client.get_guild(int(GuildId.GUILD_KVGG.value)).get_member(userId)

                if not memberDm:
                    logger.warning("Couldn't fetch member from Guild!")

                    return

                if not memberDm.dm_channel:
                    await memberDm.create_dm()

                    if not memberDm.dm_channel:
                        logger.warning("Couldnt create DM-Channel with %s!" % member.name)

                        return answer

                await memberDm.dm_channel.send(
                    "Dein %s-Timer wurde von %s beendet!" % (counter.getNameOfCounter(), username))

                return answer

            else:
                return "Es lief kein %s-Timer für %s!" % (
                    counter.getNameOfCounter(), tag)

    async def sendLogs(self, member: Member, amount: int) -> string:
        """
        Answer a given amount of Logs from our database

        :param member: Member, who requested the insight
        :param amount: Amount of Logs to be returned
        :return: string - Answer
        """
        logger.info("%s requested %d Logs" % (member.name, amount))

        if hasUserWantedRoles(member, RoleId.ADMIN, RoleId.MOD):
            with self.databaseConnection.cursor() as cursor:
                query = "SELECT discord.user_id, logs.command, logs.created_at " \
                        "FROM logs " \
                        "INNER JOIN discord " \
                        "WHERE discord_user_id = discord.id " \
                        "LIMIT %s"

                cursor.execute(query, (amount,))

                logs = cursor.fetchall()

                if not logs:
                    logger.warning("Couldn't fetch Logs!")

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

    def __del__(self):
        self.databaseConnection.close()
