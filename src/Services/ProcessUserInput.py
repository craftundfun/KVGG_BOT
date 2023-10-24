from __future__ import annotations

import asyncio
import logging
import os
import string
from datetime import datetime, timedelta

import discord
from discord import Message, Client, Member, VoiceChannel

from src.DiscordParameters.ExperienceParameter import ExperienceParameter
from src.Helper.DictionaryFuntionKeyDecorator import validateKeys
from src.Helper.GetChannelsFromCategory import getVoiceChannelsFromCategoryEnum
from src.Helper.SendDM import sendDM
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Id import ChannelId
from src.Id.Categories import TrackedCategories
from src.Id.RoleId import RoleId
from src.InheritedCommands.NameCounter import FelixCounter as FelixCounterKeyword
from src.InheritedCommands.NameCounter.BjarneCounter import BjarneCounter
from src.InheritedCommands.NameCounter.CarlCounter import CarlCounter
from src.InheritedCommands.NameCounter.CookieCounter import CookieCounter
from src.InheritedCommands.NameCounter.Counter import Counter
from src.InheritedCommands.NameCounter.FelixCounter import FelixCounter
from src.InheritedCommands.NameCounter.JjCounter import JjCounter
from src.InheritedCommands.NameCounter.OlegCounter import OlegCounter
from src.InheritedCommands.NameCounter.PaulCounter import PaulCounter
from src.InheritedCommands.NameCounter.ReneCounter import ReneCounter
from src.InheritedCommands.Times import UniversityTime, StreamTime, OnlineTime
from src.Repository.DiscordUserRepository import getDiscordUser
from src.Services.Database import Database
from src.Services.ExperienceService import ExperienceService
from src.Services.RelationService import RelationService, RelationTypeEnum
from src.Services.TTSService import TTSService
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
        if not (dcUserDb := getDiscordUser(member)):
            logger.warning("couldn't fetch DiscordUser")

            return "Es gab ein Problem!"

        dcUserDb['welcome_back_notification'] = 1 if setting else 0

        if self.__saveDiscordUserToDatabase(dcUserDb):
            logger.debug("saved changes to database")

        return "Deine Einstellung wurde erfolgreich gespeichert!"

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

            try:
                xp = ExperienceService(self.client)
            except ConnectionError as error:
                logger.error("failure to start ExperienceService", exc_info=error)
            else:
                await xp.addExperience(ExperienceParameter.XP_FOR_MESSAGE.value, member=member)

        if self.__saveDiscordUserToDatabase(dcUserDb):
            logger.debug("saved changes to database")

    def __saveDiscordUserToDatabase(self, data: dict) -> bool:
        """
        Helper to save a DiscordUser from this class into the database

        :param data: Data
        :return:
        """
        query, nones = writeSaveQuery(
            "discord",
            data['id'],
            data
        )

        if self.database.runQueryOnDatabase(query, nones):
            logger.debug("saved changed DiscordUser to database")

            return True
        logger.critical("couldn't save DiscordUser to database")

        return False

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

        async def asyncioGenerator():
            try:
                await asyncio.gather(*[member.move_to(channel) for member in membersInStartVc])
            except discord.Forbidden:
                logger.error("dont have rights move the users!")

                return "Ich habe dazu leider keine Berechtigung!"
            except discord.HTTPException as e:
                logger.warning("something went wrong!", exc_info=e)

                return "Irgendetwas ist schief gelaufen!"

        try:
            loop.run_until_complete(asyncioGenerator())
        except Exception as e:
            logger.error("something went wrong while using asyncio!", exc_info=e)

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

            return ("Du hast nicht die benötigten Rechte um Zeit hinzuzufügen!\n\n"
                    + time.getStringForTime(dcUserDb))

    @validateKeys
    async def manageWhatsAppSettings(self, member: Member, type: str, action: str, switch: str) -> str:
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
                else:
                    logger.critical("undefined entry was reached")

                    return "Es gab ein Problem."
            # !whatsapp leave
            elif action == 'leave':
                # !whatsapp leave on
                if switch == 'on':
                    whatsappSettings['receive_leave_notification'] = 1
                # !whatsapp leave off
                elif switch == 'off':
                    whatsappSettings['receive_leave_notification'] = 0
                else:
                    logger.critical("undefined entry was reached")

                    return "Es gab ein Problem."
        # !whatsapp uni
        elif type == 'Uni':
            if action == 'join':
                if switch == 'on':
                    whatsappSettings['receive_uni_join_notification'] = 1
                elif switch == 'off':
                    whatsappSettings['receive_uni_join_notification'] = 0
                else:
                    logger.critical("undefined entry was reached")

                    return "Es gab ein Problem."
            elif action == 'leave':
                if switch == 'on':
                    whatsappSettings['receive_uni_leave_notification'] = 1
                elif switch == 'off':
                    whatsappSettings['receive_uni_leave_notification'] = 0
                else:
                    logger.critical("undefined entry was reached")

                    return "Es gab ein Problem."

        query, nones = writeSaveQuery(
            "whatsapp_setting",
            whatsappSettings['id'],
            whatsappSettings
        )

        if self.database.runQueryOnDatabase(query, nones):
            logger.debug("saved changes to database")

            return "Deine Einstellung wurde übernommen!"
        else:
            logger.critical("couldn't save changes to database")

            return "Es gab ein Problem beim Speichern deiner Einstellung."

    @validateKeys
    async def sendLeaderboard(self, member: Member, type: str | None) -> string:
        """
        Returns the leaderboard of our stats in the database

        :param type:
        :param member: Member, who requested the leaderboard
        :return:
        """
        logger.debug("%s requested our leaderboard" % member.name)

        if type == "xp":
            try:
                es = ExperienceService(self.client)
            except ConnectionError as error:
                logger.error("failure to start ExperienceService", exc_info=error)

                answer = "Es ist ein Fehler aufgetreten."
            else:
                return es.sendXpLeaderboard(member=member)

        try:
            relationService = RelationService(self.client)
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

                if online := await relationService.getLeaderboardFromType(RelationTypeEnum.ONLINE, 10):
                    answer += "- __Online-Pärchen__:\n"
                    answer += online
                    answer += "\n"

                if stream := await relationService.getLeaderboardFromType(RelationTypeEnum.STREAM, 10):
                    answer += "- __Stream-Pärchen__:\n"
                    answer += stream
                    answer += "\n"

                if university := await relationService.getLeaderboardFromType(RelationTypeEnum.UNIVERSITY, 10):
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

        # check if there was no error creating the service
        if relationService in locals():
            if relationAnswer := await relationService.getLeaderboardFromType(RelationTypeEnum.ONLINE):
                answer += "\n- __Online-Pärchen__:\n"
                answer += relationAnswer

        if usersStreamTime and len(usersStreamTime) != 0:
            answer += "\n- __Stream-Zeit__:\n"

            for index, user in enumerate(usersStreamTime):
                answer += "\t%d: %s - %s\n" % (index + 1, user['username'], user['formatted_stream_time'])

        if relationService in locals():
            if relationAnswer := await relationService.getLeaderboardFromType(RelationTypeEnum.STREAM):
                answer += "\n- __Stream-Pärchen__:\n"
                answer += relationAnswer

        if usersMessageCount and len(usersMessageCount) != 0:
            answer += "\n- __Anzahl an gesendeten Nachrichten__:\n"

            for index, user in enumerate(usersMessageCount):
                answer += "\t%d: %s - %s\n" % (index + 1, user['username'], user['message_count_all_time'])

        answer += self.__leaderboardHelperCounter(usersReneCounter, ReneCounter())
        answer += self.__leaderboardHelperCounter(usersFelixCounter, FelixCounter())
        answer += self.__leaderboardHelperCounter(usersPaulCounter, PaulCounter())
        answer += self.__leaderboardHelperCounter(usersBjarneCounter, BjarneCounter())
        answer += self.__leaderboardHelperCounter(usersOlegCounter, OlegCounter())
        answer += self.__leaderboardHelperCounter(usersJjCounter, JjCounter())
        answer += self.__leaderboardHelperCounter(usersCookieCounter, CookieCounter())
        answer += self.__leaderboardHelperCounter(usersCarlCounter, CarlCounter())

        logger.debug("sending leaderboard")

        return answer

    def __leaderboardHelperCounter(self, users: list, counter: Counter) -> str:
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

        for index, user in enumerate(users, 1):
            counter.setDiscordUser(user)
            answer += "\t%d: %s - %d\n" % (index, user['username'], counter.getCounterValue())

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
        match counterName:
            case "Bjarne":
                counter = BjarneCounter()
            case "Carl":
                counter = CarlCounter()
            case "Cookie":
                counter = CookieCounter()
            case "Felix":
                counter = FelixCounter()
            case "JJ":
                counter = JjCounter()
            case "Oleg":
                counter = OlegCounter()
            case "Paul":
                counter = PaulCounter()
            case "Rene":
                counter = ReneCounter()
            case _:
                logger.critical("reached unreachable code!")

                return "Es ist ein Fehler aufgetreten!"

        logger.debug("%s requested %s-Counter" % (member.name, counter.getNameOfCounter()))

        dcUserDb = getDiscordUser(user)
        answerAppendix = ""

        if not dcUserDb:
            logger.warning("couldn't fetch DiscordUser!")

            return "Dieser Benutzer existiert (noch) nicht!"

        counter.setDiscordUser(dcUserDb)

        if not param:
            return "%s hat einen %s-Counter von %d." % (getTagStringFromId(str(user.id)),
                                                        counter.getNameOfCounter(),
                                                        counter.getCounterValue())

        try:
            value = int(param)
        except ValueError:
            logger.debug("parameter was not convertable to int")

            return "Dein eingegebener Parameter war ungültig! Bitte gib eine (korrekte) Zahl ein!"

        # user trying to add his own counters
        if int(dcUserDb['user_id']) == member.id:
            # don't allow increasing cookie counter
            if isinstance(counter, CookieCounter) and value > 0:
                logger.debug("%s tried to increase his / her own cookie-counter" % member.name)

                return "Du darfst deinen eigenen Cookie-Counter nicht erhöhen!"

            # don't allow reducing any counter
            if value < 0:
                logger.debug("%s tried to reduce his / her own counter")

                return "Du darfst deinen Counter nicht selber verringern!"

        # only allow privileged users to increase counter by great amounts
        if not hasUserWantedRoles(member, RoleId.ADMIN, RoleId.MOD) and not -1 <= value <= 1:
            logger.debug("%s wanted to edit the counter to greatly" % member.name)

            return "Du darfst einen Counter nur um -1 verringern oder +1 erhöhen!"

        # special case for cookie-counter due to xp-boost
        if isinstance(counter, CookieCounter) and value >= 1:
            counter.setCounterValue(counter.getCounterValue() + value, user, self.client)

            answerAppendix = "\n\n" + getTagStringFromId(str(user.id)) + (", du hast für deinen Keks evtl. einen neuen "
                                                                          "XP-Boost erhalten.")
        else:
            counter.setCounterValue(counter.getCounterValue() + value)

        # dont decrease to counter into negative
        if counter.getCounterValue() < 0:
            counter.setCounterValue(0)

        query, nones = writeSaveQuery(
            'discord',
            dcUserDb['id'],
            dcUserDb,
        )

        if not self.database.runQueryOnDatabase(query, nones):
            logger.critical("couldn't save changes to database")

            return "Es ist ein Fehler aufgetreten."

        # send funny TTS for Counter-Receiver
        if isinstance(counter, ReneCounter):
            if user.voice:
                logger.debug(f"playing TTS for {user.name}, because {member.name} increased the Rene-Counter")

                if value > 0:
                    tts = f"{dcUserDb['username']}, du bist dumm."
                else:
                    tts = f"{dcUserDb['username']}, du bist doch nicht dumm."

                if await TTSService().generateTTS(tts):
                    await VoiceClientService(self.client).play(user.voice.channel,
                                                               "./data/sounds/tts.mp3",
                                                               None,
                                                               True, )

        return ("Der %s-Counter von %s wurde um %d erhöht!" % (counter.getNameOfCounter(),
                                                               getTagStringFromId(str(user.id)),
                                                               value)
                + answerAppendix)

    @validateKeys
    async def handleFelixTimer(self, member: Member, user: Member, action: string, time: string = None) -> str:
        """
        Handles the Feli-Timer for the given user

        :param user: User whose timer will be edited
        :param member: Member, who raised the command
        :param action: Chosen action, start or stop
        :param time: Optional time to start the timer at
        :return:
        """
        logger.debug("handling Felix-Timer by %s" % member.name)

        dcUserDb = getDiscordUser(user)

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
            self.__saveDiscordUserToDatabase(dcUserDb)

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
            self.__saveDiscordUserToDatabase(dcUserDb)

            try:
                await sendDM(user, "Dein %s-Timer wurde beendet!" % (counter.getNameOfCounter()))
            except Exception as error:
                logger.error("couldn't send DM to %s" % dcUserDb['username'], exc_info=error)

            return "Der %s-Timer von %s wurde beendet." % (counter.getNameOfCounter(),
                                                           getTagStringFromId(str(user.id)))
