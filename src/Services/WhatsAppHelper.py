from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, List, Dict

import discord.app_commands
from discord import VoiceState, Member, Client, VoiceChannel
from discord.app_commands import Choice

from src.DiscordParameters.WhatsAppParameter import WhatsAppParameter
from src.Helper.DictionaryFuntionKeyDecorator import validateKeys
from src.Helper.GetChannelsFromCategory import getVoiceChannelsFromCategoryEnum
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Id.Categories import TrackedCategories, UniversityCategory
from src.Repository.DiscordUserRepository import getDiscordUser
from src.Repository.MessageQueueRepository import getUnsentMessagesFromTriggerUser
from src.Services.Database import Database

logger = logging.getLogger("KVGG_BOT")


class WhatsAppHelper:
    """
    Creates and manages WhatsApp-messages
    """

    def __init__(self, client: Client):
        """
        :raise ConnectionError:
        """
        self.database = Database()
        self.client = client

    def __getUsersForMessage(self) -> List[Dict[str, Any]] | None:
        """
        Returns all Users with phone number and api key including their whatsapp settings

        :return:
        """
        # not pretty but otherwise complete garbage
        query = "SELECT w.discord_user_id, w.receive_join_notification, w.receive_leave_notification, " \
                "w.receive_uni_join_notification, w.receive_uni_leave_notification, w.suspend_times, u.id, u.firstname " \
                "FROM whatsapp_setting AS w INNER JOIN user AS u ON u.discord_user_id = w.discord_user_id " \
                "WHERE u.phone_number IS NOT NULL and u.api_key_whats_app IS NOT NULL"
        users = self.database.fetchAllResults(query)

        if not users:
            logger.warning("couldn't fetch users!")

            return None

        logger.debug("fetched users for messages")

        return users

    def sendOnlineNotification(self, member: Member, update: VoiceState):
        """
        Creates an online notification, but only for allowed channels and users who are opted in

        :param member: Member that the users will be notified about
        :param update: VoiceStateUpdate
        :return:
        """
        logger.debug("creating Online-Notification for %s" % member.name)

        if member.bot:
            logger.debug("user was a bot")

            return

        # gaming channel => true, university => false, other channels => function will return
        if update.channel in getVoiceChannelsFromCategoryEnum(self.client, TrackedCategories):
            channelGaming = True
        elif update.channel in getVoiceChannelsFromCategoryEnum(self.client, UniversityCategory):
            channelGaming = False
        else:
            logger.debug("user was outside of tracked channels")

            return

        triggerDcUserDb = getDiscordUser(member)

        if not triggerDcUserDb:
            logger.warning("couldn't fetch DiscordUser!")

            return

        if not self.__canSendMessage(triggerDcUserDb, WhatsAppParameter.WAIT_UNTIL_SEND_JOIN_AFTER_LEAVE.value):
            # delete leave message if user is fast enough back online
            if not self.__canSendMessage(triggerDcUserDb, WhatsAppParameter.WAIT_UNTIL_SEND_LEAVE.value):
                self.__retractMessagesFromMessageQueue(triggerDcUserDb, False)

            logger.debug("user left and joined to fast => no message queued")

            return

        if not (users := self.__getUsersForMessage()):
            logger.debug("no users to send a message at")

            return

        for user in users:
            # dont send message to trigger user
            if user['discord_user_id'] == triggerDcUserDb['id']:
                logger.debug("dont send message to user who triggered message")

                continue

            if channelGaming and user['receive_join_notification']:
                logger.debug("message for gaming channels")

                self.__queueWhatsAppMessage(triggerDcUserDb, update.channel, user, member.name)
            elif not channelGaming and user['receive_uni_join_notification']:
                logger.debug("message for university channels")
                self.__queueWhatsAppMessage(triggerDcUserDb, update.channel, user, member.name)

    def sendOfflineNotification(self, dcUserDb: dict, update: VoiceState, member: Member):
        """
        Creates an offline notification, but only for allowed channels and users who are opted in

        :param dcUserDb: DiscordUser that caused the notification
        :param update: VoiceStateUpdate
        :param member: Member that caused the notification
        :return:
        """
        logger.debug("creating Offline-Notification for %s" % member.name)

        if lastOnline := dcUserDb['joined_at']:
            diff: timedelta = datetime.now() - lastOnline

            if diff.days <= 0:
                if diff.seconds <= WhatsAppParameter.WAIT_UNTIL_SEND_LEAVE.value * 60:
                    self.__retractMessagesFromMessageQueue(dcUserDb, True)
                    logger.debug("retracted messages from database due to fast rejoin")

                    return

        if not self.__canSendMessage(dcUserDb, WhatsAppParameter.SEND_LEAVE_AFTER_X_MINUTES_AFTER_LAST_ONLINE.value):
            logger.debug("cant send messages yet again")

            return

        if not (users := self.__getUsersForMessage()):
            logger.debug("no users for messages")

            return

        for user in users:
            if user['discord_user_id'] == dcUserDb['id']:
                logger.debug("dont sent message to trigger user")

                continue

            # use a channel id here, dcUserDb no longer holds a channel id in this method
            if (update.channel in getVoiceChannelsFromCategoryEnum(self.client, TrackedCategories)
                    and user['receive_leave_notification']):
                logger.debug("message for gaming channels")
                self.__queueWhatsAppMessage(dcUserDb, None, user, member.name)
            elif (update.channel in getVoiceChannelsFromCategoryEnum(self.client, UniversityCategory)
                  and user['receive_uni_leave_notification']):
                logger.debug("message for university channels")
                self.__queueWhatsAppMessage(dcUserDb, None, user, member.name)

    def switchChannelFromOutstandingMessages(self, dcUserDb: dict, channelName: str):
        """
        If a DiscordUser switches channel within a timeinterval the unsent message will be edited

        :param dcUserDb: DiscordUser, who changed the channels
        :param channelName: New Channel
        :return:
        """
        logger.debug("editing message from %s caused by changing channels" % dcUserDb['username'])

        if (messages := getUnsentMessagesFromTriggerUser(dcUserDb, True)) is None:
            logger.debug("no messages to edit")

            return

        if len(messages) == 0:
            logger.debug("no messages to edit")

            return

        for message in messages:
            message['message'] = dcUserDb['username'] + " ist nun im Channel " + channelName + "."

            query, nones = writeSaveQuery(
                'message_queue',
                message['id'],
                message,
            )

            if not self.database.runQueryOnDatabase(query, nones):
                logger.critical("couldn't save message to database")

        logger.debug("saved changes to database")

    def __canSendMessage(self, dcUserDb: dict, intervalTime: int) -> bool:
        """
        If the given user can send a notification based on his absence, etc.

        :param dcUserDb: DiscordUser to check
        :param intervalTime: Time to wait
        :return:
        """
        if value := dcUserDb['last_online']:
            now = datetime.now()
            diff: timedelta = now - value

            if diff.days > 0:
                return True
            elif diff.seconds > intervalTime * 60:
                return True
            else:
                return False

        return True

    def __retractMessagesFromMessageQueue(self, dcUserDb: dict, isJoinMessage: bool):
        """
        Retract messages from the queue if user left a channel fast enough

        :param dcUserDb: DiscordUser that left his channel fast enough
        :param isJoinMessage: Specify looking for join or leave messages
        :return:
        """
        logger.debug("retracting messages from queue for %s" % dcUserDb['username'])

        messages = getUnsentMessagesFromTriggerUser(dcUserDb, isJoinMessage)

        if messages is None:
            logger.debug("no messages to retract")

            return

        for message in messages:
            query = "DELETE FROM message_queue WHERE id = %s"

            if not self.database.runQueryOnDatabase(query, (message['id'],)):
                logger.critical("couldn't save to database")

    def __queueWhatsAppMessage(self, triggerDcUserDb: dict,
                               channel: VoiceChannel | None,
                               whatsappSetting: dict,
                               usernameFromTriggerUser: str):
        """
        Saves the message into the queue

        :param triggerDcUserDb: Trigger of the notification
        :param channel: Channel the user joined into
        :param whatsappSetting: User to send the message to
        :param usernameFromTriggerUser: Who triggered the message
        :return:
        """
        logger.debug("trying to queue message into database for %s" % whatsappSetting['firstname'])

        query = "SELECT channel_id FROM discord WHERE id = %s"
        dcUserDbRecipient = self.database.fetchOneResult(query, (whatsappSetting['discord_user_id'],))

        if dcUserDbRecipient is None:
            logger.warning("couldn't fetch DiscordUser!")

            return

        if dcUserDbRecipient['channel_id'] == triggerDcUserDb['channel_id']:
            logger.debug("dont send message to trigger user")

            return

        if self.__hasReceiverSuspended(whatsappSetting):
            logger.debug("receiver has suspended messages")

            return

        delay = WhatsAppParameter.DELAY_JOIN_MESSAGE.value
        timeToSent = datetime.now() + timedelta(minutes=delay)

        if not channel:
            joinMessages: list = getUnsentMessagesFromTriggerUser(triggerDcUserDb, True)

            # if there are no join message send leave
            if joinMessages is None or len(joinMessages) == 0:
                text = triggerDcUserDb['username'] + " (" + usernameFromTriggerUser + ") hat seinen Channel verlassen."
                isJoinMessage = False
            # if there is a join message, delete them and don't send leave
            else:
                self.__retractMessagesFromMessageQueue(triggerDcUserDb, True)

                return
        else:
            text = (triggerDcUserDb['username'] + " (" + usernameFromTriggerUser + ") ist nun im Channel '"
                    + channel.name + "'.")
            isJoinMessage = True

        query = "INSERT INTO message_queue (" \
                "message, user_id, created_at, time_to_sent, trigger_user_id, is_join_message" \
                ") VALUES (%s, %s, %s, %s, %s, %s)"

        self.database.runQueryOnDatabase(query,
                                         (text,
                                          whatsappSetting['id'],
                                          datetime.now(),
                                          timeToSent,
                                          triggerDcUserDb['id'],
                                          isJoinMessage,))

        logger.debug("saved new message to database")

    @validateKeys
    def addOrEditSuspendDay(self, member: Member, weekday: Choice, start: str, end: str):
        """
        Enables a given time interval for the member to not receive messages in

        :param member: Member, who requested the interval
        :param weekday: Choice of the day to edit
        :param start: Start-time
        :param end: End-time
        :return:
        """
        query = "SELECT * FROM whatsapp_setting WHERE discord_user_id = (SELECT id FROM discord WHERE user_id = %s)"

        whatsappSetting = self.database.fetchOneResult(query, (member.id,))

        if not whatsappSetting:
            logger.debug("%s is not registered for whatsapp messages" % member.name)

            return "Du bist nicht für unseren WhatsApp-Nachrichtendienst registriert!"

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
        suspendTimes = whatsappSetting['suspend_times']

        if suspendTimes is None:
            newSuspendTimes = [suspendDay]
        else:
            suspendTimes = json.loads(suspendTimes)
            newSuspendTimes = []

            alreadyExisted = False

            for day in suspendTimes:
                if day['day'] == suspendDay['day']:
                    newSuspendTimes.append(suspendDay)

                    alreadyExisted = True
                else:
                    newSuspendTimes.append(day)

            if not alreadyExisted:
                newSuspendTimes.append(suspendDay)

        whatsappSetting['suspend_times'] = json.dumps(newSuspendTimes)
        query, nones = writeSaveQuery(
            'whatsapp_setting',
            whatsappSetting['id'],
            whatsappSetting,
        )

        if self.database.runQueryOnDatabase(query, nones):
            logger.debug("saved new suspend time to database")
        else:
            return "Es gab Probleme beim speichern!"

        return "Du bekommst von nun an ab %s bis %s am %s keine WhatsApp-Nachrichten mehr." % (
            startTime.strftime("%H:%M"), endTime.strftime("%H:%M"), weekday.name)

    @validateKeys
    def resetSuspendSetting(self, member: Member, weekday: discord.app_commands.Choice):
        """
        Resets the suspend settings to None

        :param member: Member, who wishes to have his / her settings revoked
        :param weekday: Weekday to reset
        :return:
        """
        query = "SELECT * " \
                "FROM whatsapp_setting " \
                "WHERE discord_user_id = (SELECT id FROM discord WHERE user_id = %s)"
        whatsappSetting = self.database.fetchOneResult(query, (member.id,))

        if not whatsappSetting:
            logger.debug("%s is no registered for whatsapp messages" % member.name)

            return "Du bist nicht für unseren WhatsApp-Nachrichtendienst registriert!"

        suspendTimes = whatsappSetting['suspend_times']

        if not suspendTimes:
            logger.debug("no suspend times to reset")

            return "Du hast keine Suspend-Zeiten zum zurücksetzen!"

        suspendTimes = json.loads(suspendTimes)
        newSuspendTimes = []
        found = False

        for day in suspendTimes:
            if day['day'] != weekday.value:
                newSuspendTimes.append(day)
            else:
                found = True

        if len(newSuspendTimes) == 0:
            whatsappSetting['suspend_times'] = None
        else:
            whatsappSetting['suspend_times'] = json.dumps(newSuspendTimes)

        query, nones = writeSaveQuery(
            'whatsapp_setting',
            whatsappSetting['id'],
            whatsappSetting,
        )

        if self.database.runQueryOnDatabase(query, nones):
            logger.debug("saved changes to database")
        else:
            return "Es gab ein Problem."

        if found:
            return "Du bekommst nun wieder durchgehend WhatsApp-Nachrichten am %s." % weekday.name
        else:
            return "Du hattest keine Suspend-Zeit an diesem Tag festgelegt!"

    def __hasReceiverSuspended(self, whatsappSetting) -> bool:
        """
        Returns true if the receiver doesn't want messages currently.

        :return:
        """
        suspendTimes = whatsappSetting['suspend_times']

        if not suspendTimes:
            logger.debug("no suspend times found")

            return False

        suspendTimes = json.loads(suspendTimes)
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

    @validateKeys
    def listSuspendSettings(self, member: Member) -> str:
        """
        Returns all suspend settings from this member

        :param member:
        :return:
        """
        query = "SELECT * FROM whatsapp_setting WHERE discord_user_id = (SELECT id FROM discord WHERE user_id = %s)"

        whatsappSetting = self.database.fetchOneResult(query, (member.id,))

        if not whatsappSetting:
            logger.debug("%s is no registered for whatsapp messages" % member.name)

            return "Du bist nicht für unseren WhatsApp-Nachrichtendienst registriert!"

        suspendTimes = whatsappSetting['suspend_times']

        if not suspendTimes:
            logger.debug("%s has no suspend times to list" % member.name)

            return "Du hast keine Suspend-Zeiten gesetzt!"

        suspendTimes = json.loads(suspendTimes)
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

            answer += "- %s: von %s Uhr bis %s Uhr\n" % (
                days[weekday], startTime, endTime,
            )

        return answer
