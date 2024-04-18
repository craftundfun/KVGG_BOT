from __future__ import annotations

import copy
import logging
from datetime import datetime, timedelta
from typing import Any

import discord.app_commands
from discord import VoiceState, Member, Client, VoiceChannel
from discord.app_commands import Choice
from sqlalchemy import delete
from sqlalchemy import null
from sqlalchemy import select, insert
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound

from src.DiscordParameters.WhatsAppParameter import WhatsAppParameter
from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Entities.DiscordUser.Entity.WhatsappSetting import WhatsappSetting
from src.Entities.MessageQueue.Entity.MessageQueue import MessageQueue
from src.Entities.MessageQueue.Repository.MessageQueueRepository import getUnsentMessagesFromTriggerUser
from src.Entities.User.Entity.User import User
from src.Helper.GetChannelsFromCategory import getVoiceChannelsFromCategoryEnum
from src.Id.Categories import TrackedCategories, UniversityCategory
from src.Manager.DatabaseManager import getSession

logger = logging.getLogger("KVGG_BOT")


class WhatsAppHelper:
    """
    Creates and manages WhatsApp messages
    """

    def __init__(self, client: Client):
        self.client = client

    # noinspection PyMethodMayBeStatic
    def _getUsersForMessage(self, session: Session) -> list[User] | None:
        """
        Returns all Users with phone number and api key including their whatsapp settings

        :param session:
        :return:
        """
        getQuery = (select(User)
                    .where(User.phone_number.is_not(None),
                           User.api_key_whats_app.is_not(None),
                           User.discord_user_id.is_not(None), ))

        try:
            users = session.scalars(getQuery).all()
        except Exception as error:
            logger.error("couldn't fetch Settings with Users from whatsapp messages", exc_info=error)

            return None
        else:
            logger.debug("fetched users for whatsapp messages")

            # noinspection PyTypeChecker
            return list(users)

    def sendOnlineNotification(self,
                               triggerDcUserDb: DiscordUser,
                               update: VoiceState,
                               session: Session):
        """
        Creates an online notification, but only for allowed channels and settings who are opted in

        :param triggerDcUserDb: DiscordUser that caused the notification
        :param update: VoiceStateUpdate
        :param session: Session of the database connection
        :return:
        """
        logger.debug(f"creating online-whatsapp-notification for {triggerDcUserDb}")

        # gaming channel => true, university => false, other channels => function will return
        if update.channel in getVoiceChannelsFromCategoryEnum(self.client, TrackedCategories):
            channelGaming = True
        elif update.channel in getVoiceChannelsFromCategoryEnum(self.client, UniversityCategory):
            channelGaming = False
        else:
            logger.debug(f"{triggerDcUserDb} was outside of tracked channels")

            return

        if not self._canSendMessage(triggerDcUserDb, WhatsAppParameter.WAIT_UNTIL_SEND_JOIN_AFTER_LEAVE.value):
            # delete leave message if user is fast enough back online
            if not self._canSendMessage(triggerDcUserDb, WhatsAppParameter.WAIT_UNTIL_SEND_LEAVE.value):
                self._retractMessagesFromMessageQueue(triggerDcUserDb, False, session)

            logger.debug(f"{triggerDcUserDb} left and joined to fast => no message queued")

            return

        if not (users := self._getUsersForMessage(session)):
            logger.debug("no settings to send a message at")

            return

        for user in users:
            discordUser: DiscordUser = user.discord_user
            whatsappSetting: WhatsappSetting = discordUser.whatsapp_setting

            # dont send message to trigger user
            if discordUser.id == triggerDcUserDb.id:
                logger.debug("dont send message to user who triggered message")

                continue

            if channelGaming and whatsappSetting.receive_join_notification:
                logger.debug(f"whatsapp message for for gaming channels by {triggerDcUserDb}")
                self._queueWhatsAppMessage(triggerDcUserDb, update.channel, user, session)

            elif not channelGaming and whatsappSetting.receive_uni_join_notification:
                logger.debug(f"message for university channels by {triggerDcUserDb}")
                self._queueWhatsAppMessage(triggerDcUserDb, update.channel, user, session)

    def sendOfflineNotification(self, dcUserDb: DiscordUser, update: VoiceState, member: Member, session: Session):
        """
        Creates an offline notification, but only for allowed channels and users who are opted in

        :param dcUserDb: DiscordUser that caused the notification
        :param update: VoiceStateUpdate
        :param member: Member that caused the notification
        :param session: Session of the database connection
        :return:
        """
        logger.debug(f"creating Offline-Notification for {member.display_name}")

        if lastOnline := dcUserDb.joined_at:
            diff: timedelta = datetime.now() - lastOnline

            if diff.days <= 0:
                if diff.seconds <= WhatsAppParameter.WAIT_UNTIL_SEND_LEAVE.value * 60:
                    self._retractMessagesFromMessageQueue(dcUserDb, True, session)
                    logger.debug(f"retracted messages from database due to fast rejoin for {dcUserDb}")

                    return

        if not self._canSendMessage(dcUserDb, WhatsAppParameter.SEND_LEAVE_AFTER_X_MINUTES_AFTER_LAST_ONLINE.value):
            logger.debug(f"cant send messages yet again for {dcUserDb}")

            return

        if not (users := self._getUsersForMessage(session)):
            logger.debug(f"no users for messages by {dcUserDb}")

            return

        for user in users:
            if user.discord_user_id == dcUserDb.id:
                logger.debug("dont sent message to trigger user")

                continue

            if not (dcUserDbReceiver := user.discord_user):
                logger.error(f"{user} has no DiscordUser")

                continue

            if not (whatsappSetting := dcUserDbReceiver.whatsapp_setting):
                logger.error(f"{dcUserDbReceiver} has no WhatsappSetting")

                continue

            # use a channel id here, dcUserDb no longer holds a channel id in this method
            if (update.channel in getVoiceChannelsFromCategoryEnum(self.client, TrackedCategories)
                    and whatsappSetting.receive_leave_notification):
                logger.debug(f"message for gaming channels by {dcUserDb}")
                self._queueWhatsAppMessage(dcUserDb, None, user, session)

            elif (update.channel in getVoiceChannelsFromCategoryEnum(self.client, UniversityCategory)
                  and whatsappSetting.receive_uni_leave_notification):
                logger.debug(f"message for university channels by {dcUserDb}")
                self._queueWhatsAppMessage(dcUserDb, None, user, session)

    def switchChannelFromOutstandingMessages(self,
                                             dcUserDb: DiscordUser,
                                             channelName: str,
                                             member: Member,
                                             session: Session, ):
        """
        If a DiscordUser switches channel within a timeinterval the unsent message will be edited

        :param dcUserDb: DiscordUser, who changed the channels
        :param channelName: New Channel
        :param member: Member-Object of the user to get the names correctly
        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        logger.debug(f"editing message from {dcUserDb} caused by changing channels")

        if not (messages := getUnsentMessagesFromTriggerUser(dcUserDb, True, session)):
            logger.debug(f"no messages to edit for {dcUserDb}")

            return

        if len(messages) == 0:
            logger.debug(f"no messages to edit for {dcUserDb}")

            return

        for message in messages:
            message.message = f"{member.display_name} ({member.name}) ist nun im Channel {channelName}."

        try:
            session.commit()
        except Exception as error:
            logger.error(f"couldn't commit changes to {messages}", exc_info=error)
        else:
            logger.debug(f"saved changes to database for {dcUserDb}")

    def _canSendMessage(self, dcUserDb: DiscordUser, intervalTime: int) -> bool:
        """
        If the given user can send a notification based on his absence, etc.

        :param dcUserDb: DiscordUser to check
        :param intervalTime: Time to wait
        :return:
        """
        if value := dcUserDb.last_online:
            now = datetime.now()
            diff: timedelta = now - value

            if diff.days > 0:
                return True
            elif diff.seconds > intervalTime * 60:
                return True
            else:
                return False

        return True

    def _retractMessagesFromMessageQueue(self, dcUserDb: DiscordUser, isJoinMessage: bool, session: Session):
        """
        Retract messages from the queue if user left a channel fast enough

        :param dcUserDb: DiscordUser that left his channel fast enough
        :param isJoinMessage: Specify looking for join or leave messages
        :return:
        """
        logger.debug(f"retracting messages from queue for {dcUserDb}")

        messages = getUnsentMessagesFromTriggerUser(dcUserDb, isJoinMessage, session)

        if not messages:
            logger.debug(f"no messages to retract for {dcUserDb}")

            return

        for message in messages:
            # noinspection PyTypeChecker
            deleteQuery = delete(MessageQueue).where(MessageQueue.id == message.id)

            try:
                session.execute(deleteQuery)
            except Exception as error:
                logger.error(f"couldn't delete MessageQueue for {message}", exc_info=error)

                return

        try:
            session.commit()
        except Exception as error:
            logger.error(f"couldn't delete {messages} from database", exc_info=error)

    def _queueWhatsAppMessage(self,
                              triggerDcUserDb: DiscordUser,
                              channel: VoiceChannel | None,
                              receiverUser: User,
                              session: Session):
        """
        Saves the message into the queue

        :param triggerDcUserDb: Trigger of the notification
        :param channel: Channel the user joined into
        :param session:
        :return:
        """
        logger.debug(f"trying to queue message into database for {receiverUser.discord_user}")

        receiverDiscordUser: DiscordUser = receiverUser.discord_user
        receiverWhatsappSetting: WhatsappSetting = receiverDiscordUser.whatsapp_setting

        if receiverDiscordUser.channel_id == triggerDcUserDb.channel_id:
            logger.debug("dont send message to trigger user")

            return

        if self._hasReceiverSuspended(receiverWhatsappSetting):
            logger.debug("receiver has suspended messages")

            return

        delay = WhatsAppParameter.DELAY_JOIN_MESSAGE.value
        timeToSent = datetime.now() + timedelta(minutes=delay)

        if not channel:
            joinMessages: list = getUnsentMessagesFromTriggerUser(triggerDcUserDb, True, session)

            # if there are no join message send leave
            if joinMessages is None or len(joinMessages) == 0:
                text = (f"{triggerDcUserDb.username} ({triggerDcUserDb.discord_name}) hat seinen / ihren Channel "
                        f"verlassen.")
                isJoinMessage = False
            # if there is a join message, delete them and don't send leave
            else:
                self._retractMessagesFromMessageQueue(triggerDcUserDb, True, session)

                return
        else:
            text = f"{triggerDcUserDb.username} ({triggerDcUserDb.discord_name}) ist nun im Channel '{channel.name}'."
            isJoinMessage = True

        insertQuery = insert(MessageQueue).values(message=text,
                                                  user_id=receiverUser.id,
                                                  created_at=datetime.now(),
                                                  time_to_sent=timeToSent,
                                                  trigger_user_id=triggerDcUserDb.id,
                                                  is_join_message=isJoinMessage, )

        try:
            session.execute(insertQuery)
            session.commit()
        except Exception as error:
            logger.error(f"couldn't save message to database for {receiverUser.discord_user}", exc_info=error)
            session.rollback()

            return
        else:
            logger.debug(f"saved new message to database by {triggerDcUserDb} for {receiverUser.discord_user}")

    # noinspection PyMethodMayBeStatic
    def addOrEditSuspendDay(self, member: Member, weekday: Choice, start: str, end: str) -> str:
        """
        Enables a given time interval for the member to not receive messages in

        :param member: Member, who requested the interval
        :param weekday: Choice of the day to edit
        :param start: Start-time
        :param end: End-time
        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        if not (session := getSession()):  # TODO outside
            return "Es gab einen Fehler!"

        # noinspection PyTypeChecker
        getQuery = (select(WhatsappSetting)
                    .where(WhatsappSetting.discord_user_id == (select(DiscordUser.id)
                                                               .where(DiscordUser.user_id == str(member.id))
                                                               .scalar_subquery())))

        try:
            whatsappSetting = session.scalars(getQuery).one()
        except NoResultFound:
            logger.debug(f"{member.display_name} is not registered for whatsapp messages")
            session.close()

            return "Du bist nicht für unseren Whatsapp-Nachrichtendienst registriert!"
        except Exception as error:
            logger.error(f"couldn't fetch WhatsappSettings for {member.display_name}", exc_info=error)
            session.close()

            return "Es gab einen Fehler!"

        current = datetime.now()

        try:
            startTime: datetime = datetime.strptime(start, "%H:%M")
            startTime = startTime.replace(year=current.year, month=current.month, day=current.day)
        except ValueError:
            logger.debug("starting time was incorrect")

            return "Bitte wähle eine korrekte Startzeit aus!"

        try:
            endTime: datetime = datetime.strptime(end, "%H:%M")
            endTime = endTime.replace(year=current.year, month=current.month, day=current.day)
        except ValueError:
            logger.debug("ending time was incorrect")

            return "Bitte wähle eine korrekt Endzeit aus!"

        if endTime.hour < startTime.hour:
            logger.debug("ending time was earlier than starting time")

            return "Deine Endzeit kann nicht früher als die Startzeit sein!"
        elif endTime == startTime:
            logger.debug("interval was 0 minutes")

            return "Dein Intervall beträgt 0 Minuten!"

        suspendDay: dict = {
            'day': weekday.value,
            'start': str(startTime),
            'end': str(endTime),
        }
        suspendTimes: list[dict[str, Any]] | None = copy.deepcopy(whatsappSetting.suspend_times)

        if not suspendTimes:
            newSuspendTimes = [suspendDay]
        else:
            newSuspendTimes = []
            alreadyExisted = False

            for time in suspendTimes:
                if time['day'] == suspendDay['day']:
                    newSuspendTimes.append(suspendDay)

                    alreadyExisted = True
                else:
                    newSuspendTimes.append(time)

            if not alreadyExisted:
                newSuspendTimes.append(suspendDay)

        whatsappSetting.suspend_times = newSuspendTimes

        try:
            session.commit()
        except Exception as error:
            logger.error(f"couldn't save changes for WhatsappSetting for {member.display_name}", exc_info=error)
            session.rollback()
            session.close()

            return "Es gab einen Fehler!"

        session.close()

        return (f"Du bekommst von nun an ab {startTime.strftime('%H:%M')} bis {endTime.strftime('%H:%M')} am "
                f"{weekday.name} keine WhatsApp-Nachrichten mehr.")

    def resetSuspendSetting(self, member: Member, weekday: discord.app_commands.Choice):
        """
        Resets the suspend settings to None

        :param member: Member, who wishes to have his / her settings revoked
        :param weekday: Weekday to reset
        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        if not (session := getSession()):  # TODO outside
            return "Es gab einen Fehler!"

        # noinspection PyTypeChecker
        getQuery = (select(WhatsappSetting)
                    .where(WhatsappSetting.discord_user_id == (select(DiscordUser.id)
                                                               .where(DiscordUser.user_id == str(member.id))
                                                               .scalar_subquery())))

        try:
            whatsappSetting = session.scalars(getQuery).one()
        except NoResultFound:
            logger.debug(f"{member.display_name} is not registered for whatsapp messages")
            session.close()

            return "Du bist nicht für unseren WhatsApp-Nachrichtendienst registriert!"
        except Exception as error:
            logger.error(f"couldn't fetch WhatsappSettings for {member.display_name}", exc_info=error)
            session.close()

            return "Es gab einen Fehler!"

        suspendTimes: list[dict[str, Any]] | None = copy.deepcopy(whatsappSetting.suspend_times)

        if not suspendTimes:
            logger.debug(f"no suspend times to reset for {member.display_name}")
            session.close()

            return "Du hast keine Suspend-Zeiten zum zurücksetzen!"

        newSuspendTimes = []
        found = False

        for time in suspendTimes:
            if time['day'] != weekday.value:
                newSuspendTimes.append(time)
            else:
                found = True

        whatsappSetting.suspend_times = newSuspendTimes if len(newSuspendTimes) > 0 else null()

        try:
            session.commit()
        except Exception as error:
            logger.error(f"couldn't commit WhatsappSettings for {member.display_name}", exc_info=error)
            session.rollback()
            session.close()

            return "Es gab einen Fehler!"

        session.close()

        if found:
            logger.debug(f"reset suspend times for {member.display_name} on {weekday.name}")

            return f"Du bekommst nun wieder durchgehend WhatsApp-Nachrichten am {weekday.name}."
        else:
            logger.debug(f"{member.display_name} had no suspend times on {weekday.name} to reset")

            return "Du hattest keine Suspend-Zeit an diesem Tag festgelegt!"

    def _hasReceiverSuspended(self, whatsappSetting: WhatsappSetting) -> bool:
        """
        Returns true if the receiver doesn't want messages currently.

        :return:
        """
        suspendTimes = whatsappSetting.suspend_times

        if not suspendTimes:
            logger.debug(f"no suspend times found for {whatsappSetting.discord_user}")

            return False

        now = datetime.now()

        for day in suspendTimes:
            # if we have the correct day
            if int(day['day']) - 1 == now.weekday():
                # if the time is correct
                startTime: datetime = datetime.strptime(day['start'], "%Y-%m-%d %H:%M:%S")
                endTime: datetime = datetime.strptime(day['end'], "%Y-%m-%d %H:%M:%S")

                if startTime.time() < now.time() < endTime.time():
                    return True
                else:
                    return False

    def listSuspendSettings(self, member: Member) -> str:
        """
        Returns all suspend settings from this member

        :param member:
        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        if not (session := getSession()):  # TODO outside
            return "Es gab einen Fehler!"

        # noinspection PyTypeChecker
        getQuery = (select(WhatsappSetting)
                    .where(WhatsappSetting.discord_user_id == (select(DiscordUser.id)
                                                               .where(DiscordUser.user_id == str(member.id))
                                                               .scalar_subquery())))

        try:
            whatsappSetting = session.scalars(getQuery).one()
        except NoResultFound:
            logger.debug(f"{member.display_name} is not registered for whatsapp messages")
            session.close()

            return "Du bist nicht für unseren WhatsApp-Nachrichtendienst registriert!"
        except Exception as error:
            logger.error(f"couldn't fetch WhatsappSettings for {member.display_name}", exc_info=error)
            session.close()

            return "Es gab einen Fehler!"

        if not (suspendTimes := copy.deepcopy(whatsappSetting.suspend_times)):
            logger.debug(f"{member.display_name} has not suspend times to list")
            session.close()

            return "Du hast keine Suspend-Zeiten gesetzt!"

        answer = "Du hast folgende Suspend-Zeiten:\n\n"

        days = {
            "1": "Montag",
            "2": "Dienstag",
            "3": "Mittwoch",
            "4": "Donnerstag",
            "5": "Freitag",
            "6": "Samstag",
            "7": "Sonntag",
        }

        # to give the sort function the key to sort from
        def sort_key(dictionary):
            return dictionary["day"]

        suspendTimes = sorted(suspendTimes, key=sort_key)

        for day in suspendTimes:
            startTime = datetime.strptime(day['start'], "%Y-%m-%d %H:%M:%S")
            startTime = startTime.strftime("%H:%M")
            endTime = datetime.strptime(day['end'], "%Y-%m-%d %H:%M:%S")
            endTime = endTime.strftime("%H:%M")
            weekday = day["day"]

            answer += f"- {days[weekday]}: von {startTime} Uhr bis {endTime} Uhr\n"

        session.close()

        return answer
