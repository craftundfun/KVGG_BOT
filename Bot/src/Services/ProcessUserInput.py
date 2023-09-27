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
from discord import Message, Client, Member, VoiceChannel

from Bot.src.DiscordParameters.ExperienceParameter import ExperienceParameter
from Bot.src.Helper import WriteSaveQuery
from Bot.src.Helper.DictionaryFuntionKeyDecorator import validateKeys
from Bot.src.Helper.SendDM import sendDM
from Bot.src.Id import ChannelId
from Bot.src.Id.ChannelIdWhatsAppAndTracking import ChannelIdWhatsAppAndTracking
from Bot.src.Id.ChatCommand import ChatCommand
from Bot.src.Id.RoleId import RoleId
from Bot.src.InheritedCommands.NameCounter import Counter, JjCounter, ReneCounter, PaulCounter, OlegCounter, \
    CookieCounter, CarlCounter, FelixCounter, BjarneCounter
from Bot.src.InheritedCommands.Times import UniversityTime, OnlineTime, StreamTime
from Bot.src.Repository.DiscordUserRepository import getDiscordUser
from Bot.src.Services import QuotesManager
from Bot.src.Services.Database import Database
from Bot.src.Services.ExperienceService import ExperienceService
from Bot.src.Services.RelationService import RelationService, RelationTypeEnum

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

    :param tag: Tag from Discord
    :return: int - user id
    """
    try:
        return int(tag[2:len(tag) - 1])
    except ValueError:
        logger.debug("couldn't convert %s into id" % tag)

        return None


def getTagStringFromId(tag: str) -> str:
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
        """
        :param client:
        :raise ConnectionError:
        """
        self.database = Database()
        self.client = client

    @validateKeys
    def changeWelcomeBackNotificationSetting(self, member: Member, setting: bool) -> str:
        """
        Changes the notification setting for coming online

        :param member:
        :param setting:
        :return:
        """
        # TODO make extra class for changing settings

        if not (dcUserDb := getDiscordUser(member)):
            logger.warning("couldn't fetch DiscordUser")

            return "Es gab ein Problem!"

        dcUserDb['welcome_back_notification'] = 1 if setting else 0

        self.__saveDiscordUserToDatabase(dcUserDb)
        logger.debug("saved changes to database")

        return "Deine Einstellung wurde erfolgreich gespeichert!"

    @DeprecationWarning
    async def processMessage(self, message: Message):
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
        # await es.addExperience(ExperienceParameter.XP_FOR_MESSAGE.value, dcUserDb)

        self.__saveDiscordUserToDatabase(dcUserDb)

    async def raiseMessageCounter(self, member: Member, channel):
        """
        Increases the message count if the given user if he / she used an interaction

        :param member: Member, who called the interaction
        :param channel: Channel, where the interaction was used
        :return:
        """
        logger.debug("increasing message-count for %s" % member.name)

        dcUserDb = getDiscordUser(member)

        if dcUserDb is None:
            logger.warning("couldn't fetch DiscordUser!")
        elif channel is None:
            logger.warning("no channel provided")

        if channel.id != int(ChannelId.ChannelId.CHANNEL_BOT_TEST_ENVIRONMENT.value) and SECRET_KEY:
            logger.debug("can grant an increase of the message counter")

            if dcUserDb['message_count_all_time']:
                dcUserDb['message_count_all_time'] = dcUserDb['message_count_all_time'] + 1
            else:
                dcUserDb['message_count_all_time'] = 1

            try:
                xp = ExperienceService(self.client)
            except ConnectionError as error:
                logger.error("failure to start ExperienceService", exc_info=error)
            else:
                await xp.addExperience(ExperienceParameter.XP_FOR_MESSAGE.value, member=member)

        logger.debug("saved changes to database")
        self.__saveDiscordUserToDatabase(dcUserDb)

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

    def __saveDiscordUserToDatabase(self, data):
        """
        Helper to save a DiscordUser from this class into the database

        :param data: Data
        :return:
        """
        query, nones = WriteSaveQuery.writeSaveQuery(
            "discord",
            data['id'],
            data
        )

        if self.database.runQueryOnDatabase(query, nones):
            logger.debug("saved changed DiscordUser to database")
        else:
            logger.critical("couldn't save DiscordUser to database")

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

    @validateKeys
    async def answerJoke(self, member: Member, category: str):
        """
        Answers a joke from an API

        :param member: Member, who requested the joke
        :param category: Optional category of the joke - might not work due to API limitations
        :return:
        """
        logger.debug("%s requested a joke" % member.name)

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

    @validateKeys
    async def moveUsers(self, channel: VoiceChannel, member: Member) -> string:
        """
        Moves all users from the initiator channel to the given one

        :param channel: Chosen channel to move user to
        :param member: Member who initiated the move
        :return:
        """
        logger.debug("%s requested to move users into %s" % (member.name, channel.name))

        if not member.voice or not (channelStart := member.voice.channel):
            logger.debug("member is not connected to a voice channel")

            return "Du bist mit keinem Voicechannel verbunden!"
        elif str(channelStart.id) not in ChannelIdWhatsAppAndTracking.getValues() and not hasUserWantedRoles(member,
                                                                                                             RoleId.ADMIN,
                                                                                                             RoleId.MOD):
            logger.debug("starting channel is not allowed to be moved")

            return "Dein aktueller Channel befindet sich außerhalb des erlaubten Channel-Spektrums!"

        if channelStart == channel:
            logger.debug("starting and destination channel are the same")

            return "Alle befinden sich bereits in diesem Channel!"

        if (str(channel.id) not in ChannelIdWhatsAppAndTracking.getValues()
                and not hasUserWantedRoles(member, RoleId.ADMIN, RoleId.MOD)):
            logger.debug("destination channel is outside of the allowed moving range")

            return "Dieser Channel befindet sich außerhalb des erlaubten Channel-Spektrums!"

        canProceed = False

        for role in member.roles:
            permissions = channel.permissions_for(role)
            if permissions.view_channel and permissions.connect:
                canProceed = True

                break

        if not canProceed:
            logger.debug("user has no rights to use the move command")

            return "Du hast keine Berechtigung in diesen Channel zu moven!"

        membersInStartVc = channelStart.members
        loop = asyncio.get_event_loop()

        async def asyncioGenerator():
            try:
                await asyncio.gather(*[member.move_to(channel) for member in membersInStartVc])
            except discord.Forbidden:
                logger.error("dont have rights move the users!")

                return "Ich habe dazu leider keine Berechtigung!"
            except discord.HTTPException as e:
                logger.warning("Something went wrong!", exc_info=e)

                return "Irgendetwas ist schief gelaufen!"

        try:
            loop.run_until_complete(asyncioGenerator())
        except Exception as e:
            logger.error("Somthing went wrong while using asyncio!", exc_info=e)

            return "Irgendetwas ist schief gelaufen!"

        logger.debug("moved all users without problems")

        return "Alle User wurden erfolgreich verschoben!"

    @validateKeys
    async def accessTimeAndEdit(self, timeName: str, user: Member, member: Member, param: int | None) -> str:
        """
        Answering given Time from given User or adds (subtracts) given amount

        :param user: Requested user
        :param timeName: Time-type
        :param member: Requesting Member
        :param param: Optional amount of time added or subtracted
        :return:
        """
        time = None

        if timeName == "online":
            time = OnlineTime.OnlineTime()
        elif timeName == "stream":
            time = StreamTime.StreamTime()
        elif timeName == "uni":
            time = UniversityTime.UniversityTime()

        logger.debug("%s requested %s-Time" % (member.name, time.getName()))

        # all users
        """
        if userTag == 'all' and param and hasUserWantedRoles(member, RoleId.ADMIN, RoleId.MOD):
            logger.debug("increasing time of all online users")

            try:
                correction = int(param)
            except ValueError:
                logger.debug("given string couldn't be converted to a number")

                return "Deine Korrektur war keine Zahl!"

            users = getOnlineUsers(self.databaseConnection)

            if users is None:
                logger.debug("no one is online")

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
        """
        dcUserDb = getDiscordUser(user)

        if not dcUserDb or not time.getTime(dcUserDb) or time.getTime(dcUserDb) == 0:
            if not dcUserDb:
                logger.warning("couldn't fetch DiscordUser!")

            logger.debug("user has not been online yet")

            return "Dieser Benutzer war noch nie online!"

        if param and hasUserWantedRoles(member, RoleId.ADMIN, RoleId.MOD):
            logger.debug("has permission to increase time")

            try:
                correction = int(param)
            except ValueError:
                logger.debug("parameter was not convertable to int")

                return "Deine Korrektur war keine Zahl!"

            onlineBefore = time.getTime(dcUserDb)

            time.increaseTime(dcUserDb, correction)

            onlineAfter = time.getTime(dcUserDb)
            self.__saveDiscordUserToDatabase(dcUserDb)

            logger.debug("saved changes to database")

            return ("Die %s-Zeit von <@%s> wurde von %s Minuten auf %s Minuten korrigiert!"
                    % (time.getName(), dcUserDb['user_id'], onlineBefore, onlineAfter))
        else:
            logger.debug("returning time")

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

    @validateKeys
    async def manageWhatsAppSettings(self, member: Member, type: str, action: str, switch: str):
        """
        Lets the user change their WhatsApp settings

        :param member: Member, who requested a change of his / her settings
        :param type: Type of messages (gaming or university)
        :param action: Action of the messages (join or leave)
        :param switch: Switch (on / off)
        :return:
        """
        logger.debug("%s requested a change of his / her WhatsApp settings" % member.name)

        query = "SELECT * " \
                "FROM whatsapp_setting " \
                "WHERE discord_user_id = (SELECT id FROM discord WHERE user_id = %s)"

        whatsappSettings = self.database.fetchOneResult(query, (member.id,))

        if not whatsappSettings:
            logger.warning("couldn't fetch corresponding settings!")

            return "Du bist nicht als User bei uns registriert!"

        if type == 'Gaming':
            # !whatsapp join
            if action == 'join':
                # !whatsapp join on
                if switch == 'on':
                    whatsappSettings['receive_join_notification'] = 1

                # !whatsapp join off
                elif switch == 'off':
                    whatsappSettings['receive_join_notification'] = 0

            # !whatsapp leave
            elif action == 'leave':
                # !whatsapp leave on
                if switch == 'on':
                    whatsappSettings['receive_leave_notification'] = 1

                # !whatsapp leave off
                elif switch == 'off':
                    whatsappSettings['receive_leave_notification'] = 0

        # !whatsapp uni
        elif type == 'Uni':
            if action == 'join':
                if switch == 'on':
                    whatsappSettings['receive_uni_join_notification'] = 1
                elif switch == 'off':
                    whatsappSettings['receive_uni_join_notification'] = 0

            elif action == 'leave':
                if switch == 'on':
                    whatsappSettings['receive_uni_leave_notification'] = 1
                elif switch == 'off':
                    whatsappSettings['receive_uni_leave_notification'] = 0

        query, nones = WriteSaveQuery.writeSaveQuery(
            "whatsapp_setting",
            whatsappSettings['id'],
            whatsappSettings
        )

        if self.database.runQueryOnDatabase(query, nones):
            logger.debug("saved changes to database")

            return "Deine Einstellung wurde übernommen!"
        else:
            logger.critical("couldn't save changes to database")

            return "Es gab ein Problem beim speichern deiner Einstellungen."

    @validateKeys
    async def sendLeaderboard(self, member: Member, type: str | None) -> string:
        """
        Returns the leaderboard of our stats in the database

        :param type:
        :param member: Member, who requested the leaderboard
        :return:
        """
        logger.debug("%s requested our leaderboard" % member.name)

        try:
            rs = RelationService(self.client)
        except ConnectionError as error:
            logger.error("failure to start RelationService", exc_info=error)

            if type == "relations":
                return "Es gab ein Problem."
        else:
            if type == "relations":
                logger.debug("leaderboard for relations")

                answer = "----------------------------\n"
                answer += "__**Leaderboard - Relationen**__\n"
                answer += "----------------------------\n\n"

                if online := await rs.getLeaderboardFromType(RelationTypeEnum.ONLINE, 10):
                    answer += "- __Online-Pärchen__:\n"
                    answer += online
                    answer += "\n"

                if stream := await rs.getLeaderboardFromType(RelationTypeEnum.STREAM, 10):
                    answer += "- __Stream-Pärchen__:\n"
                    answer += stream
                    answer += "\n"

                if university := await rs.getLeaderboardFromType(RelationTypeEnum.UNIVERSITY, 10):
                    answer += "- __Lern-Pärchen__:\n"
                    answer += university
                    answer += "\n"

                return answer

        # online time
        query = "SELECT username, formated_time " \
                "FROM discord " \
                "WHERE time_online IS NOT NULL " \
                "ORDER BY time_online DESC " \
                "LIMIT 3"

        usersOnlineTime = self.database.fetchAllResults(query)

        # stream time
        query = "SELECT username, formatted_stream_time " \
                "FROM discord " \
                "WHERE time_streamed IS NOT NULL " \
                "ORDER BY time_streamed DESC " \
                "LIMIT 3"

        usersStreamTime = self.database.fetchAllResults(query)

        # message count
        query = "SELECT username, message_count_all_time " \
                "FROM discord " \
                "WHERE message_count_all_time != 0 " \
                "ORDER BY message_count_all_time DESC " \
                "LIMIT 3"

        usersMessageCount = self.database.fetchAllResults(query)

        # Rene counter
        query = "SELECT username, rene_counter " \
                "FROM discord " \
                "WHERE rene_counter != 0 " \
                "ORDER BY rene_counter DESC " \
                "LIMIT 3"

        usersReneCounter = self.database.fetchAllResults(query)

        # Felix counter
        query = "SELECT username, felix_counter " \
                "FROM discord " \
                "WHERE felix_counter != 0 " \
                "ORDER BY felix_counter DESC " \
                "LIMIT 3"

        usersFelixCounter = self.database.fetchAllResults(query)

        # Paul counter
        query = "SELECT username, paul_counter " \
                "FROM discord " \
                "WHERE paul_counter != 0 " \
                "ORDER BY paul_counter DESC " \
                "LIMIT 3"

        usersPaulCounter = self.database.fetchAllResults(query)

        # Bjarne counter
        query = "SELECT username, bjarne_counter " \
                "FROM discord " \
                "WHERE bjarne_counter != 0 " \
                "ORDER BY bjarne_counter DESC " \
                "LIMIT 3"

        usersBjarneCounter = self.database.fetchAllResults(query)

        # JJ counter
        query = "SELECT username, jj_counter " \
                "FROM discord " \
                "WHERE jj_counter != 0 " \
                "ORDER BY jj_counter DESC " \
                "LIMIT 3"

        usersJjCounter = self.database.fetchAllResults(query)

        # Oleg counter
        query = "SELECT username, oleg_counter " \
                "FROM discord " \
                "WHERE oleg_counter != 0 " \
                "ORDER BY oleg_counter DESC " \
                "LIMIT 3"

        usersOlegCounter = self.database.fetchAllResults(query)

        # Carl counter
        query = "SELECT username, carl_counter " \
                "FROM discord " \
                "WHERE carl_counter != 0 " \
                "ORDER BY carl_counter DESC " \
                "LIMIT 3"

        usersCarlCounter = self.database.fetchAllResults(query)

        # Cookie counter
        query = "SELECT username, cookie_counter " \
                "FROM discord " \
                "WHERE cookie_counter != 0 " \
                "ORDER BY cookie_counter DESC " \
                "LIMIT 3"

        usersCookieCounter = self.database.fetchAllResults(query)

        answer = "--------------\n"
        answer += "__**Leaderboard**__\n"
        answer += "--------------\n\n"

        if usersOnlineTime and len(usersOnlineTime) != 0:
            answer += "- __Online-Zeit__:\n"

            for index, user in enumerate(usersOnlineTime):
                answer += "\t%d: %s - %s\n" % (index + 1, user['username'], user['formated_time'])

        if relationAnswer := await rs.getLeaderboardFromType(RelationTypeEnum.ONLINE):
            answer += "\n- __Online-Pärchen__:\n"
            answer += relationAnswer

        del relationAnswer

        if usersStreamTime and len(usersStreamTime) != 0:
            answer += "\n- __Stream-Zeit__:\n"

            for index, user in enumerate(usersStreamTime):
                answer += "\t%d: %s - %s\n" % (index + 1, user['username'], user['formatted_stream_time'])

        if relationAnswer := await rs.getLeaderboardFromType(RelationTypeEnum.STREAM):
            answer += "\n- __Stream-Pärchen__:\n"
            answer += relationAnswer

        if usersMessageCount and len(usersMessageCount) != 0:
            answer += "\n- __Anzahl an gesendeten Nachrichten__:\n"

            for index, user in enumerate(usersMessageCount):
                answer += "\t%d: %s - %s\n" % (index + 1, user['username'], user['message_count_all_time'])

        answer += self.__leaderboardHelperCounter(usersReneCounter, ReneCounter.ReneCounter())
        answer += self.__leaderboardHelperCounter(usersFelixCounter, FelixCounter.FelixCounter())
        answer += self.__leaderboardHelperCounter(usersPaulCounter, PaulCounter.PaulCounter())
        answer += self.__leaderboardHelperCounter(usersBjarneCounter, BjarneCounter.BjarneCounter())
        answer += self.__leaderboardHelperCounter(usersOlegCounter, OlegCounter.OlegCounter())
        answer += self.__leaderboardHelperCounter(usersJjCounter, JjCounter.JjCounter())
        answer += self.__leaderboardHelperCounter(usersCookieCounter, CookieCounter.CookieCounter())
        answer += self.__leaderboardHelperCounter(usersCarlCounter, CarlCounter.CarlCounter())

        logger.debug("sending leaderboard")

        return answer

    def __leaderboardHelperCounter(self, users, counter: Counter) -> string:
        """
        Helper for listing a leaderboard entry for given counter

        :param users: List of users
        :param counter: counter-type
        :return:
        """
        if not users:
            logger.debug("user list was none")

            return ""
        elif len(users) < 1:
            logger.debug("user list was empty")

            return ""

        answer = "\n- __%s-Counter__:\n" % counter.getNameOfCounter()

        for index, user in enumerate(users):
            counter.setDiscordUser(user)
            answer += "\t%d: %s - %d\n" % (index + 1, user['username'], counter.getCounterValue())

        return answer

    @validateKeys
    async def sendRegistrationLink(self, member: Member):
        """
        Sends an individual invitaion link to the member who requested it

        :param member:
        :return:
        """
        logger.debug("%s request a registration link" % member.name)

        link = "https://axellotl.de/register/"
        link += str(member.id)

        try:
            await sendDM(member, "Dein persönlicher Link zum registrieren: %s" % link)
        except Exception as error:
            logger.error("couldnt send DM to %s" % member.name, exc_info=error)

            return "Es gab Probleme dir eine Nachricht zu schreiben!"

        logger.debug("sent dm to requester")

        return "Dir wurde das Formular privat gesendet!"

    # TODO improve code duplicates. working but kinda shitty
    @validateKeys
    async def accessNameCounterAndEdit(self, counterName: str,
                                       user: Member,
                                       member: Member,
                                       param: int | None) -> string:
        """
        Answering given Counter from given User or adds (subtracts) given amount

        :param user: User which counter was requested
        :param counterName: Chosen counter-type
        :param member: Member who requested the counter
        :param param: Optional amount of time to add / subtract
        :return:
        """
        # counter = None

        if "Bjarne" == counterName:
            counter = BjarneCounter.BjarneCounter()
        elif "Carl" == counterName:
            counter = CarlCounter.CarlCounter()
        elif "Cookie" == counterName:
            counter = CookieCounter.CookieCounter()
        elif "Felix" == counterName:
            counter = FelixCounter.FelixCounter()
        elif "JJ" == counterName:
            counter = JjCounter.JjCounter()
        elif "Oleg" == counterName:
            counter = OlegCounter.OlegCounter()
        elif "Paul" == counterName:
            counter = PaulCounter.PaulCounter()
        elif "Rene" == counterName:
            counter = ReneCounter.ReneCounter()
        else:
            logger.critical("reached unreachable code!")

            return "Es ist ein Fehler aufgetreten!"

        logger.debug("%s requested %s-Counter" % (member.name, counter.getNameOfCounter()))

        dcUserDb = getDiscordUser(user)
        answerAppendix = ""

        if not dcUserDb:
            logger.warning("couldn't fetch DiscordUser!")

            return "Dieser Benutzer existiert (noch) nicht!"

        counter.setDiscordUser(dcUserDb)

        # increase counter and member is Mod / Admin to overwrite the limit to increase
        if param and hasUserWantedRoles(member, RoleId.ADMIN, RoleId.MOD):
            try:
                value = int(param)
            except ValueError:
                logger.debug("parameter was not convertable to int")

                return "Dein eingegebener Parameter war ungültig! Bitte gib eine Zahl ein!"

            # cant increase own cookie counter to avoid xp-boost abuse
            if isinstance(counter, CookieCounter.CookieCounter):
                if int(dcUserDb['user_id']) == member.id and value > 0:
                    logger.debug("%s tried to increase his own cookie-counter" % member.name)

                    return "Du darfst deinen eigenen Cookie-Counter nicht erhöhen!"

            if int(dcUserDb['user_id']) == member.id and value < 0:
                logger.debug("%s tried to reduce his own counter" % member.name)

                return "Du darfst deinen eigenen Counter nicht verringern!"

            # special case for Cookie-Counter
            if isinstance(counter, CookieCounter.CookieCounter):
                if counter.getCounterValue() + value >= 0:
                    counter.setCounterValue(counter.getCounterValue() + value, user, self.client)

                    answerAppendix = ("\n\n"
                                      + getTagStringFromId(str(user.id))
                                      + ", du hast für deinen Keks evtl. einen neuen XP-Boost erhalten. "
                                        "Schau mal nach!")
                else:
                    counter.setCounterValue(0, user, self.client)
            # dont go negative
            elif counter.getCounterValue() + value < 0:
                counter.setCounterValue(0)
            else:
                counter.setCounterValue(counter.getCounterValue() + value)

            query, nones = WriteSaveQuery.writeSaveQuery(
                'discord',
                dcUserDb['id'],
                dcUserDb
            )

            if not self.database.runQueryOnDatabase(query, nones):
                logger.critical("couldnt save changes to database")

                return "Es ist ein Fehler aufgetreten!"

            logger.debug("saved changes to database")

            return ("Der %s-Counter von %s wurde um %d erhöht!" % (
                counter.getNameOfCounter(), getTagStringFromId(str(user.id)), value)
                    + answerAppendix)
        # param but no privileged user
        elif param:
            try:
                value = int(param)
            except ValueError:
                logger.debug("parameter was not convertable to int")

                return "Dein eingegebener Parameter war ungültig!"

            # cant increase own cookie counter to avoid xp-boost abuse
            if isinstance(counter, CookieCounter.CookieCounter):
                if int(dcUserDb['user_id']) == member.id and value > 0:
                    logger.debug("%s tried to increase his own cookie-counter" % member.name)

                    return "Du darfst deinen eigenen Cookie-Counter nicht erhöhen!"

            if int(dcUserDb['user_id']) == member.id and value < 0:
                logger.debug("%s tried to reduce his own counter" % member.name)

                return "Du darfst deinen eigenen Counter nicht verringern!"
            elif value == 0:
                logger.debug("%s tried to reduce counter with 0" % member.name)

                return "0 ist keine gültige Anpassung!"

            value = 1 if value >= 0 else -1

            # special case for Cookie-Counter
            if isinstance(counter, CookieCounter.CookieCounter):
                if counter.getCounterValue() + value >= 0:
                    counter.setCounterValue(counter.getCounterValue() + value, user, self.client)

                    answerAppendix = ("\n\n"
                                      + getTagStringFromId(str(user.id))
                                      + ", du hast für deinen Keks evtl. einen neuen XP-Boost erhalten. "
                                        "Schau mal nach!")
                else:
                    counter.setCounterValue(0, user, self.client)
            # dont go negative
            elif counter.getCounterValue() + value < 0:
                counter.setCounterValue(0)
            else:
                counter.setCounterValue(counter.getCounterValue() + value)

            query, nones = WriteSaveQuery.writeSaveQuery(
                'discord',
                dcUserDb['id'],
                dcUserDb
            )

            if not self.database.runQueryOnDatabase(query, nones):
                logger.critical("couldn't save changes to database")

                return "Es ist ein Fehler aufgetreten!"

            logger.debug("saved changes to database")

            return ("Der %s-Counter von %s wurde um %d erhöht!" % (
                counter.getNameOfCounter(), getTagStringFromId(str(user.id)), value)
                    + answerAppendix)
        else:
            query, nones = WriteSaveQuery.writeSaveQuery(
                'discord',
                dcUserDb['id'],
                dcUserDb
            )

            if not self.database.runQueryOnDatabase(query, nones):
                logger.critical("couldn't save changes to database")

                return "Es ist ein Fehler aufgetreten!"

            return "%s hat einen %s-Counter von %d!" % (
                getTagStringFromId(str(user.id)), counter.getNameOfCounter(), counter.getCounterValue())

    @validateKeys
    async def handleFelixTimer(self, member: Member, user: Member, action: string, time: string = None):
        """
        Handles the Feli-Timer for the given user

        :param user: User whose timer will be edited
        :param member: Member, who raised the command
        :param action: Chosen action, start or stop
        :param time: Optional time to start the timer at
        :return:
        """
        logger.debug("Handling Felix-Timer by %s" % member.name)

        dcUserDb = getDiscordUser(user)

        if not dcUserDb:
            logger.warning("couldn't fetch DiscordUser!")

            return "Bitte tagge deinen User korrekt!"

        counter = FelixCounter.FelixCounter(dcUserDb)

        if action == "start":
            logger.debug("start chosen")

            if dcUserDb['channel_id'] is None and counter.getFelixTimer() is None:
                date = None

                if time:
                    try:
                        timeToStart = datetime.strptime(time, "%H:%M")
                        current = datetime.now()
                        timeToStart = timeToStart.replace(year=current.year, month=current.month, day=current.day)

                        # if the time is set to the next day
                        if timeToStart < datetime.now():
                            timeToStart = timeToStart + timedelta(days=1)

                        date = timeToStart
                    except ValueError:
                        try:
                            minutesFromNow = int(time)
                        except ValueError:
                            logger.debug("no time or amount of minutes was given")

                            return ("Bitte gib eine gültige Zeit an! Zum Beispiel: '20' für 20 Minuten oder '09:04' um "
                                    "den Timer um 09:04 Uhr zu starten!")

                        timeToStart = datetime.now() + timedelta(minutes=minutesFromNow)
                        date = timeToStart
                else:
                    date = datetime.now()

                if not date:
                    logger.debug("no date was given")

                    return "Deine gegebene Zeit war inkorrekt. Bitte achte auf das Format: '09:09' oder '20'!"

                link = FelixCounter.LIAR

                if member.nick:
                    username = member.nick
                else:
                    username = member.name

                counter.setFelixTimer(date)
                self.__saveDiscordUserToDatabase(dcUserDb)

                answer = "Der %s-Timer von %s wird um %s Uhr gestartet!" % (
                    counter.getNameOfCounter(), getTagStringFromId(str(user.id)), date.strftime("%H:%M"))

                try:
                    await sendDM(user, "Dein %s-Timer wurde von %s auf %s Uhr gesetzt! Pro Minute "
                                       "bekommst du ab dann einen %s-Counter dazu! Um den Timer zu "
                                       "stoppen komm (vorher) online oder 'warte' ab dem Zeitpunkt 20 "
                                       "Minuten!\n"
                                 % (
                                     counter.getNameOfCounter(),
                                     username, date.strftime("%H:%M"),
                                     counter.getNameOfCounter(),
                                 ))
                    await sendDM(user, link)
                except Exception as error:
                    logger.error("couldn't send DM to %s" % user.name, exc_info=error)

                logger.debug("send dms to %s" % user.name)

                return answer

            elif dcUserDb['channel_id'] is not None:
                logger.debug("%s is online" % user.name)

                return "%s ist gerade online, du kannst für ihn / sie keinen %s-Timer starten!" % (
                    getTagStringFromId(str(user.id)), counter.getNameOfCounter())

            elif counter.getFelixTimer() is not None:
                logger.debug("Felix-Timer is already running")

                return "Es läuft bereits ein Timer!"

            else:
                logger.critical("No matching condition were found for starting a Felix-Timer!")

                return "Es ist ein Fehler aufgetreten!"

        elif action == "stop":
            logger.debug("stop chosen")

            if counter.getFelixTimer() is not None:
                if counter.getDiscordUser()['user_id'] == str(member.id):
                    logger.debug("user wanted to stop his / her own Felix-Timer")

                    return "Du darfst deinen eigenen Felix-Timer nicht beenden! Komm doch einfach online!"

                counter.setFelixTimer(None)

                if member.nick:
                    username = member.nick
                else:
                    username = member.name

                answer = ("Der %s-Timer von %s wurde beendet!"
                          % (counter.getNameOfCounter(), getTagStringFromId(str(user.id))))

                self.__saveDiscordUserToDatabase(dcUserDb)

                try:
                    await sendDM(user, "Dein %s-Timer wurde von %s beendet!" % (counter.getNameOfCounter(), username))
                except Exception as error:
                    logger.error("couldnt send DM to %s" % dcUserDb['username'], exc_info=error)

                logger.debug("sent dm to %s" % user.name)

                return answer

            else:
                return "Es lief kein %s-Timer für %s!" % (
                    counter.getNameOfCounter(), getTagStringFromId(str(user.id)))

    @DeprecationWarning
    @validateKeys
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
