from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

import discord
from discord import Message, Client, Member, VoiceChannel

from src.DiscordParameters.ExperienceParameter import ExperienceParameter
from src.DiscordParameters.StatisticsParameter import StatisticsParameter
from src.Entities.DiscordUser.Repository.DiscordUserRepository import getDiscordUser
from src.Helper.GetChannelsFromCategory import getVoiceChannelsFromCategoryEnum
from src.Helper.MoveMembesToVoicechannel import moveMembers
from src.Helper.ReadParameters import getParameter, Parameters
from src.Helper.SendDM import sendDM
from src.Id.Categories import TrackedCategories
from src.Id.ChannelId import ChannelId
from src.Id.RoleId import RoleId
from src.InheritedCommands.NameCounter import FelixCounter as FelixCounterKeyword
from src.InheritedCommands.Times import UniversityTime, StreamTime, OnlineTime
from src.Manager.DatabaseManager import getSession
from src.Manager.StatisticManager import StatisticManager
from src.Services.ExperienceService import ExperienceService
from src.Services.GameDiscordService import GameDiscordService
from src.Services.QuestService import QuestService, QuestType
from src.Services.RelationService import RelationService
from src.Services.VoiceClientService import VoiceClientService

logger = logging.getLogger("KVGG_BOT")


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
        self.gameDiscordService = GameDiscordService(self.client)

    async def raiseMessageCounter(self, member: Member, channel, command: bool = False):
        """
        Increases the message count if the given user if he / she used an interaction

        :param member: Member, who called the interaction
        :param channel: Channel, where the interaction was used
        :param command: Whether the message was a command.
        If yes, the Quest won't be checked for a message.
        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        logger.debug(f"increasing message-count for {member.display_name}")

        if not channel:
            logger.error("no channel provided")

            return

        if member.bot:
            logger.debug(f"{member.display_name} was a bot")

            return

        if not (session := getSession()):
            return

        if not (dcUserDb := getDiscordUser(member, session)):
            logger.error("couldn't fetch DiscordUser!")

            return

        if channel.id != ChannelId.CHANNEL_BOT_TEST_ENVIRONMENT.value or not getParameter(Parameters.PRODUCTION):
            logger.debug(f"can grant an increase of the message counter for {dcUserDb}")

            if command:
                self.statisticManager.increaseStatistic(StatisticsParameter.COMMAND, member, session)

                dcUserDb.command_count_all_time += 1
            else:
                await self.questService.addProgressToQuest(member, QuestType.MESSAGE_COUNT)
                self.statisticManager.increaseStatistic(StatisticsParameter.MESSAGE, member, session)
                await self.experienceService.addExperience(ExperienceParameter.XP_FOR_MESSAGE.value,
                                                           member=member, )

                dcUserDb.message_count_all_time += 1
        else:
            logger.debug(f"can't grant an increase of the message counter for {dcUserDb}")

        try:
            session.commit()
        except Exception as error:
            logger.error(f"could not commit: {dcUserDb}", exc_info=error)
        finally:
            session.close()

    async def moveUsers(self, channel: VoiceChannel, member: Member) -> str:
        """
        Moves all users from the initiator channel to the given one

        :param channel: Chosen channel to move user to
        :param member: Member who initiated the move
        :return:
        """
        logger.debug(f"{member.display_name} requested to move users into {channel.name}")

        if not member.voice or not (channelStart := member.voice.channel):
            logger.debug(f"{member.display_name} is not connected to a voice channel")

            return "Du bist mit keinem Voicechannel verbunden!"
        elif channelStart not in (categoryChannels := getVoiceChannelsFromCategoryEnum(self.client, TrackedCategories)):
            logger.debug(f"{channelStart.name} is not allowed to be moved")

            return "Dein aktueller Channel befindet sich außerhalb des erlaubten Channel-Spektrums!"

        if channelStart == channel:
            logger.debug("starting and destination channel are the same")

            return "Alle befinden sich bereits in diesem Channel!"

        if channel not in categoryChannels:
            logger.debug(f"{channel.name} is outside of the allowed moving range")

            return "Dieser Channel befindet sich außerhalb des erlaubten Channel-Spektrums!"

        canProceed = False

        for role in member.roles:
            permissions = channel.permissions_for(role)

            if permissions.view_channel and permissions.connect:
                canProceed = True

                break

        if not canProceed:
            logger.debug(f"{member.display_name} has no rights to use the move command")

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
        if timeName == "online":
            time = OnlineTime.OnlineTime()
        elif timeName == "stream":
            time = StreamTime.StreamTime()
        elif timeName == "uni":
            time = UniversityTime.UniversityTime()
        else:
            logger.error(f"undefined entry was reached: {timeName}")

            return "Es gab ein Problem!"

        logger.debug(f"{member.name} requested {time.getName()}-Time from {user.display_name}")

        if not (session := getSession()):
            return "Es gab ein Problem!"

        if not (dcUserDb := getDiscordUser(user, session)):
            logger.error(f"couldn't fetch DiscordUser for {user.display_name}")
            session.close()

            return "Es gab ein Problem!"

        if time.getTime(dcUserDb) == 0 and not param:
            logger.debug(f"{user.display_name} has not been online yet")
            session.close()

            return "Dieser Benutzer war noch nie online!"

        if param and hasUserWantedRoles(member, RoleId.ADMIN, RoleId.MOD):
            logger.debug(f"{member.display_name} has permission to increase time")

            try:
                correction = int(param)
            except ValueError:
                logger.debug(f"parameter was not convertable to int: {param}")
                session.close()

                return "Deine Korrektur war keine Zahl!"

            onlineBefore = time.getTime(dcUserDb)

            time.increaseTime(dcUserDb, correction)

            onlineAfter = time.getTime(dcUserDb)

            if onlineAfter < 0:
                logger.debug("value after increase was < 0")
                session.rollback()
                session.close()

                return "Die korrigierte Zahl ist kleiner als 0! Bitte verwende eine andere Korrektur!"

            try:
                session.commit()
            except Exception as error:
                logger.error(f"could not commit DiscordUser of {user.display_name}", exc_info=error)
                session.rollback()

                return "Es gab ein Problem!"
            finally:
                session.close()

            if isinstance(time, OnlineTime.OnlineTime):
                self.statisticManager.increaseStatistic(StatisticsParameter.ONLINE, user, session, correction)

                logger.debug(f"increased statistics for {user.display_name}")
            elif isinstance(time, StreamTime.StreamTime):
                self.statisticManager.increaseStatistic(StatisticsParameter.STREAM, user, session, correction)

                logger.debug(f"increased statistics for {user.display_name}")

            return (f"Die {time.getName()}-Zeit von <@{user.id}> wurde von {onlineBefore} Minuten auf "
                    f"{onlineAfter} Minuten korrigiert!")
        elif param and not hasUserWantedRoles(member, RoleId.ADMIN, RoleId.MOD):
            logger.debug(f"returning time for {user.display_name} because {member.display_name} has no rights to "
                         f"increase")
            session.close()

            return ("Du hast nicht die benötigten Rechte um Zeit hinzuzufügen!\n\n"
                    + time.getStringForTime(dcUserDb))
        else:
            session.close()

            return time.getStringForTime(dcUserDb)

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

    async def handleFelixTimer(self,
                               requestingMember: Member,
                               requestedMember: Member,
                               action: str,
                               time: str = None) -> str:
        """
        Handles the Feli-Timer for the given user

        :param requestedMember: User whose timer will be edited
        :param requestingMember: Member, who raised the command
        :param action: Chosen action, start or stop
        :param time: Optional time to start the timer at
        :return:
        """
        logger.debug(f"handling Felix-Timer for {requestedMember.display_name} by {requestingMember.display_name}")

        if not (session := getSession()):
            return "Es gab ein Problem!"

        if not (dcUserDb := getDiscordUser(requestedMember, session)):
            logger.error(f"couldn't fetch DiscordUser for {requestedMember.display_name}")
            session.close()

            return "Es gab einen Fehler!"

        if action == FelixCounterKeyword.FELIX_COUNTER_START_KEYWORD:
            logger.debug(f"start chosen by {requestingMember.display_name}")

            if dcUserDb.felix_counter_start:
                logger.debug(f"Felix-Timer is already running for {requestedMember.display_name}")
                session.close()

                return "Es läuft bereits ein Timer!"

            if dcUserDb.channel_id:
                logger.debug(f"{requestedMember.display_name} is online")
                session.close()

                return (f"<@{requestedMember.id}> ist gerade online. Du kannst für ihn / sie keinen Felix-Timer "
                        f"starten!")

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
                        logger.debug(f"no time or amount of minutes was given by {requestingMember.display_name}, "
                                     f"value: {time}")
                        session.close()

                        return ("Bitte gib eine gültige Zeit an! Zum Beispiel: '20' für 20 Minuten oder '09:04' um den "
                                "Timer um 09:04 Uhr zu starten!")

                    timeToStart = datetime.now() + timedelta(minutes=minutesFromNow)
                    date = timeToStart

            # I don't think it's necessary, but don't change a running system (too much)
            if not date:
                logger.debug(f"no date was given by {requestingMember.display_name}")
                session.close()

                return "Deine gegebene Zeit war inkorrekt. Bitte achte auf das Format: '09:09' oder '20'!"

            dcUserDb.felix_counter_start = date

            try:
                session.commit()
            except Exception as error:
                logger.error(f"couldn't commit changes for DiscordUser of {requestedMember.display_name}",
                             exc_info=error, )
                session.rollback()
                session.close()

                return "Es gab einen Fehler!"

            session.close()

            try:
                await sendDM(requestedMember, f"Dein Felix-Timer wurde von {requestingMember.display_name} auf "
                                              f"{date.strftime('%H:%M')} Uhr gesetzt! Pro vergangener Minute bekommst "
                                              f"du ab der Uhrzeit einen Felix-Counter dazu! Um den Timer zu stoppen "
                                              f"komm (vorher) online oder 'warte' ab dem Zeitpunkt 20 Minuten!\n")
                await sendDM(requestedMember, FelixCounterKeyword.LIAR)
            except Exception as error:
                logger.error(f"couldn't send DM to {requestedMember.display_name}", exc_info=error)

                return (f"Der Felix-Timer wurde gestellt. {requestedMember.display_name} wurde allerdings nicht "
                        f"darüber informiert - es gab Probleme beim Senden einer DM.")
            else:
                logger.debug(f"notified {requestedMember.display_name} about his / her Felix-Timer by "
                             f"{requestingMember.display_name}")

                return f"Der Felix-Timer von <@{requestedMember.id}> wird um {date.strftime('%H:%M')} Uhr gestartet."
        else:
            logger.debug(f"stop chosen by {requestingMember.display_name}")

            if not dcUserDb.felix_counter_start:
                logger.debug(f"{requestedMember.display_name} had no running Felix-Timer")
                session.close()

                return f"Es lief kein Felix-Timer für <@{requestedMember.id}>!"

            if requestedMember.id == requestingMember.id:
                logger.debug(f"{requestingMember.display_name} wanted to stop his / her own Felix-Timer")
                session.close()

                return "Du darfst deinen eigenen Felix-Timer nicht beenden! Komm doch einfach online!"

            dcUserDb.felix_counter_start = None

            try:
                session.commit()
            except Exception as error:
                logger.error(f"couldn't save changes for DiscordUser for {requestedMember.display_name}",
                             exc_info=error, )
                session.rollback()
                session.close()

                return "Es gab einen Fehler!"

            session.close()

            try:
                await sendDM(requestedMember, "Dein Felix-Timer wurde beendet!")
            except Exception as error:
                logger.error(f"couldn't send DM to {requestedMember.display_name}", exc_info=error)

            return f"Der Felix-Timer von <@{requestedMember.id}> wurde beendet."
