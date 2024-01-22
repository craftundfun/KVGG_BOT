from __future__ import annotations

import asyncio
import logging
import os
import string
from datetime import datetime, timedelta

import discord
from discord import Message, Client, Member, VoiceChannel

from src.DiscordParameters.ExperienceParameter import ExperienceParameter
from src.DiscordParameters.StatisticsParameter import StatisticsParameter
from src.Helper.GetChannelsFromCategory import getVoiceChannelsFromCategoryEnum
from src.Helper.MoveMembesToVoicechannel import moveMembers
from src.Helper.SendDM import sendDM
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Id import ChannelId
from src.Id.Categories import TrackedCategories
from src.Id.RoleId import RoleId
from src.InheritedCommands.NameCounter import FelixCounter as FelixCounterKeyword
from src.InheritedCommands.NameCounter.FelixCounter import FelixCounter
from src.InheritedCommands.Times import UniversityTime, StreamTime, OnlineTime
from src.Repository.DiscordUserRepository import getDiscordUser
from src.Services.Database import Database
from src.Services.ExperienceService import ExperienceService
from src.Services.QuestService import QuestService, QuestType
from src.Services.RelationService import RelationService, RelationTypeEnum
from src.Services.StatisticManager import StatisticManager
from src.Services.VoiceClientService import VoiceClientService

logger = logging.getLogger("KVGG_BOT")
SECRET_KEY = os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False)


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
        self.client = client

        self.questService = QuestService(self.client)
        self.experienceService = ExperienceService(self.client)
        self.relationService = RelationService(self.client)
        self.voiceClientService = VoiceClientService(self.client)
        self.statisticManager = StatisticManager(self.client)

    async def raiseMessageCounter(self, member: Member, channel, command: bool = False):
        """
        Increases the message count if the given user if he / she used an interaction

        :param member: Member, who called the interaction
        :param channel: Channel, where the interaction was used
        :param command: Whether the message was a command.
        If yes, the Quest won't be checked for a message.
        :raise ConnectionError: If the database connection cant be established
        :return:
        """
        logger.debug("increasing message-count for %s" % member.name)

        database = Database()
        dcUserDb = getDiscordUser(member, database)

        if dcUserDb is None:
            logger.warning("couldn't fetch DiscordUser!")

            return
        elif channel is None:
            logger.warning("no channel provided")

            return

        # if we are in docker, don't count a message from the test environment
        if channel.id != ChannelId.ChannelId.CHANNEL_BOT_TEST_ENVIRONMENT.value and SECRET_KEY:
            logger.debug("can grant an increase of the message counter")

            # message_count_all_time can be None -> None-safe operation
            if dcUserDb['message_count_all_time']:
                dcUserDb['message_count_all_time'] = dcUserDb['message_count_all_time'] + 1
            else:
                dcUserDb['message_count_all_time'] = 1

            if not command:
                await self.questService.addProgressToQuest(member, QuestType.MESSAGE_COUNT)
                self.statisticManager.increaseStatistic(StatisticsParameter.MESSAGE, member)
            else:
                self.statisticManager.increaseStatistic(StatisticsParameter.COMMAND, member)

            await self.experienceService.addExperience(ExperienceParameter.XP_FOR_MESSAGE.value, member=member)

        if self._saveDiscordUserToDatabase(dcUserDb, database):
            logger.debug("saved changes to database")

    def _saveDiscordUserToDatabase(self, data: dict, database: Database) -> bool:
        """
        Helper to save a DiscordUser from this class into the database

        :param data: Data
        :param database:
        :return:
        """
        query, nones = writeSaveQuery(
            "discord",
            data['id'],
            data
        )

        if database.runQueryOnDatabase(query, nones):
            logger.debug("saved changed DiscordUser to database")

            return True

        logger.critical("couldn't save DiscordUser to database")

        return False

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
        elif channelStart not in getVoiceChannelsFromCategoryEnum(self.client, TrackedCategories):
            logger.debug("starting channel is not allowed to be moved")

            return "Dein aktueller Channel befindet sich außerhalb des erlaubten Channel-Spektrums!"

        if channelStart == channel:
            logger.debug("starting and destination channel are the same")

            return "Alle befinden sich bereits in diesem Channel!"

        if channel not in getVoiceChannelsFromCategoryEnum(self.client, TrackedCategories):
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

        try:
            loop.run_until_complete(moveMembers(membersInStartVc, channel))
        except discord.Forbidden:
            logger.error("dont have rights move the users!")

            return "Ich habe dazu leider keine Berechtigung!"
        except discord.HTTPException as e:
            logger.warning("something went wrong!", exc_info=e)

            return "Irgendetwas ist schief gelaufen!"
        except Exception as e:
            logger.error("something went wrong while using asyncio!", exc_info=e)

            return "Irgendetwas ist schief gelaufen!"

        logger.debug("moved all users without problems")

        return "Alle User wurden erfolgreich verschoben!"

    async def accessTimeAndEdit(self, timeName: str, user: Member, member: Member, param: int | None) -> str:
        """
        Answering given Time from given User or adds (subtracts) given amount

        :param user: Requested user
        :param timeName: Time-type
        :param member: Requesting Member
        :param param: Optional amount of time added or subtracted
        :raise ConnectionError: If the database connection cant be established
        :return:
        """
        database = Database()

        if timeName == "online":
            time = OnlineTime.OnlineTime()
        elif timeName == "stream":
            time = StreamTime.StreamTime()
        elif timeName == "uni":
            time = UniversityTime.UniversityTime()
        else:
            logger.critical("undefined entry was reached!")

            return "Es gab ein Problem"

        logger.debug("%s requested %s-Time" % (member.name, time.getName()))

        dcUserDb = getDiscordUser(user, database)

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
            self._saveDiscordUserToDatabase(dcUserDb, database)

            logger.debug("saved changes to database")

            if isinstance(time, OnlineTime.OnlineTime):
                self.statisticManager.increaseStatistic(StatisticsParameter.ONLINE, user, correction)

                logger.debug(f"increased statistics for {user.display_name}")
            elif isinstance(time, StreamTime.StreamTime):
                self.statisticManager.increaseStatistic(StatisticsParameter.STREAM, user, correction)

                logger.debug(f"increased statistics for {user.display_name}")

            return ("Die %s-Zeit von <@%s> wurde von %s Minuten auf %s Minuten korrigiert!"
                    % (time.getName(), dcUserDb['user_id'], onlineBefore, onlineAfter))
        elif param and not hasUserWantedRoles(member, RoleId.ADMIN, RoleId.MOD):
            logger.debug("returning time")

            return ("Du hast nicht die benötigten Rechte um Zeit hinzuzufügen!\n\n"
                    + time.getStringForTime(dcUserDb))
        else:
            return time.getStringForTime(dcUserDb)

    async def sendLeaderboard(self, member: Member, type: str | None) -> string:
        """
        Returns the leaderboard of our stats in the database

        :param type:
        :param member: Member, who requested the leaderboard
        :raise ConnectionError: If the database connection cant be established
        :return:
        """
        logger.debug("%s requested our leaderboard" % member.name)

        database = Database()

        if type == "xp":
            return self.experienceService.sendXpLeaderboard(member=member)

        if type == "relations":
            logger.debug("leaderboard for relations")

            answer = "----------------------------\n"
            answer += "__**Leaderboard - Relationen**__\n"
            answer += "----------------------------\n\n"

            if online := await self.relationService.getLeaderboardFromType(RelationTypeEnum.ONLINE, 10):
                answer += "- __Online-Pärchen__:\n"
                answer += online
                answer += "\n"

            if stream := await self.relationService.getLeaderboardFromType(RelationTypeEnum.STREAM, 10):
                answer += "- __Stream-Pärchen__:\n"
                answer += stream
                answer += "\n"

            if university := await self.relationService.getLeaderboardFromType(RelationTypeEnum.UNIVERSITY, 10):
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

        usersOnlineTime = database.fetchAllResults(query)

        # stream time
        query = "SELECT username, formatted_stream_time " \
                "FROM discord " \
                "ORDER BY time_streamed DESC " \
                "LIMIT 3"

        usersStreamTime = database.fetchAllResults(query)

        # message count
        query = "SELECT username, message_count_all_time " \
                "FROM discord " \
                "WHERE message_count_all_time != 0 " \
                "ORDER BY message_count_all_time DESC " \
                "LIMIT 3"

        usersMessageCount = database.fetchAllResults(query)

        answer = "--------------\n"
        answer += "__**Leaderboard**__\n"
        answer += "--------------\n\n"

        if usersOnlineTime and len(usersOnlineTime) != 0:
            answer += "- __Online-Zeit__:\n"

            for index, user in enumerate(usersOnlineTime):
                answer += "\t%d: %s - %s\n" % (index + 1, user['username'], user['formated_time'])

        if relationAnswer := await self.relationService.getLeaderboardFromType(RelationTypeEnum.ONLINE):
            answer += "\n- __Online-Pärchen__:\n"
            answer += relationAnswer

        if usersStreamTime and len(usersStreamTime) != 0:
            answer += "\n- __Stream-Zeit__:\n"

            for index, user in enumerate(usersStreamTime):
                answer += "\t%d: %s - %s\n" % (index + 1, user['username'], user['formatted_stream_time'])

        if relationAnswer := await self.relationService.getLeaderboardFromType(RelationTypeEnum.STREAM):
            answer += "\n- __Stream-Pärchen__:\n"
            answer += relationAnswer

        if usersMessageCount and len(usersMessageCount) != 0:
            answer += "\n- __Anzahl an gesendeten Nachrichten__:\n"

            for index, user in enumerate(usersMessageCount):
                answer += "\t%d: %s - %s\n" % (index + 1, user['username'], user['message_count_all_time'])

        # circular import
        from src.Services.CounterService import CounterService
        answer += CounterService.leaderboardForCounter(database)

        logger.debug("sending leaderboard")

        return answer

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
            logger.error("couldn't send DM to %s" % member.name, exc_info=error)

            return "Es gab Probleme dir eine Nachricht zu schreiben!"

        logger.debug("sent dm to requester")

        return "Dir wurde das Formular privat gesendet!"

    async def handleFelixTimer(self, member: Member, user: Member, action: string, time: string = None) -> str:
        """
        Handles the Feli-Timer for the given user

        :param user: User whose timer will be edited
        :param member: Member, who raised the command
        :param action: Chosen action, start or stop
        :param time: Optional time to start the timer at
        :raise ConnectionError: If the database connection cant be established
        :return:
        """
        logger.debug("handling Felix-Timer by %s" % member.name)

        database = Database()
        dcUserDb = getDiscordUser(user, database)

        if not dcUserDb:
            logger.warning("couldn't fetch DiscordUser!")

            return "Bitte tagge deinen User korrekt!"

        counter = FelixCounter(dcUserDb)

        if action == FelixCounterKeyword.FELIX_COUNTER_START_KEYWORD:
            if counter.getFelixTimer():
                logger.debug("felix-Timer is already running")

                return "Es läuft bereits ein Timer!"

            if dcUserDb['channel_id']:
                logger.debug("%s is online" % user.name)

                return ("%s ist gerade online. Du kannst für ihn / sie keinen %s-Timer starten!" %
                        (getTagStringFromId(str(user.id)), counter.getNameOfCounter()))

            if not time:
                date = datetime.now()
            else:
                # user gave time of day
                try:
                    timeToStart = datetime.strptime(time, "%H:%M")
                    current = datetime.now()
                    timeToStart = timeToStart.replace(year=current.year, month=current.month, day=current.day)

                    # if the time is set to the next day
                    if timeToStart < datetime.now():
                        timeToStart = timeToStart + timedelta(days=1)

                    date = timeToStart
                except ValueError:
                    # user gave minutes from now instead
                    try:
                        minutesFromNow = int(time)
                    except ValueError:
                        logger.debug("no time or amount of minutes was given")

                        return ("Bitte gib eine gültige Zeit an! Zum Beispiel: '20' für 20 Minuten oder '09:04' um den "
                                "Timer um 09:04 Uhr zu starten!")

                    timeToStart = datetime.now() + timedelta(minutes=minutesFromNow)
                    date = timeToStart

            # I don't think it's necessary, but don't change a running system (too much)
            if not date:
                logger.debug("no date was given")

                return "Deine gegebene Zeit war inkorrekt. Bitte achte auf das Format: '09:09' oder '20'!"

            counter.setFelixTimer(date)
            self._saveDiscordUserToDatabase(dcUserDb, database)

            try:
                await sendDM(user, "Dein %s-Timer wurde von %s auf %s Uhr gesetzt! Pro vergangener Minute "
                                   "bekommst du ab der Uhrzeit einen %s-Counter dazu! Um den Timer zu stoppen komm "
                                   "(vorher) online oder 'warte' ab dem Zeitpunkt 20 Minuten!\n"
                             % (counter.getNameOfCounter(),
                                member.nick if member.nick else member.name,
                                date.strftime("%H:%M"),
                                counter.getNameOfCounter())
                             )
                await sendDM(user, FelixCounterKeyword.LIAR)
            except Exception as error:
                logger.error("couldn't send DM to %s" % user.name, exc_info=error)
            else:
                logger.debug("send DMs to %s" % user.name)

                return "Der %s-Timer von %s wird um %s Uhr gestartet." % (counter.getNameOfCounter(),
                                                                          getTagStringFromId(str(user.id)),
                                                                          date.strftime("%H:%M"))
        else:
            logger.debug("stop chosen")

            if counter.getFelixTimer() is None:
                return "Es lief kein %s-Timer für %s!" % (counter.getNameOfCounter(), getTagStringFromId(str(user.id)))

            if str(counter.getDiscordUser()['user_id']) == str(member.id):
                logger.debug("user wanted to stop his / her own Felix-Timer")

                return "Du darfst deinen eigenen Felix-Timer nicht beenden! Komm doch einfach online!"

            counter.setFelixTimer(None)
            self._saveDiscordUserToDatabase(dcUserDb, database)

            try:
                await sendDM(user, "Dein %s-Timer wurde beendet!" % (counter.getNameOfCounter()))
            except Exception as error:
                logger.error("couldn't send DM to %s" % dcUserDb['username'], exc_info=error)

            return "Der %s-Timer von %s wurde beendet." % (counter.getNameOfCounter(),
                                                           getTagStringFromId(str(user.id)))
