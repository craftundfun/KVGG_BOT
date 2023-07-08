from __future__ import annotations

import logging
import string

from datetime import datetime, timedelta
from typing import Any, List, Dict

from discord import VoiceState, Member
from src.DiscordParameters.WhatsAppParameter import WhatsAppParameter
from src.Helper import WriteSaveQuery
from src.Id.ChannelIdWhatsAppAndTracking import ChannelIdWhatsAppAndTracking
from src.Id.ChannelIdUniversityTracking import ChannelIdUniversityTracking
from src.Repository.DiscordUserRepository import getDiscordUser
from src.Repository.MessageQueueRepository import getUnsendMessagesFromTriggerUser
from src.Helper.CreateNewDatabaseConnection import getDatabaseConnection

logger = logging.getLogger("KVGG_BOT")


class WhatsAppHelper:
    """
    Creates and manages WhatsApp-messages
    """

    def __init__(self):
        self.databaseConnection = getDatabaseConnection()

    def __getUsersForMessage(self) -> List[Dict[str, Any]] | None:
        """
        Returns all Users with phone number and api key including their whatsapp settings

        :return:
        """
        with self.databaseConnection.cursor() as cursor:
            # not pretty but otherwise complete garbage
            query = "SELECT w.discord_user_id, w.receive_join_notification, w.receive_leave_notification, " \
                    "w.receive_uni_join_notification, w.receive_uni_leave_notification, w.suspend_start, " \
                    "w.suspend_end, u.id " \
                    "FROM whatsapp_setting AS w INNER JOIN user AS u ON u.discord_user_id = w.discord_user_id " \
                    "WHERE u.phone_number IS NOT NULL and u.api_key_whats_app IS NOT NULL"

            cursor.execute(query)

            data = cursor.fetchall()

            if data is None:
                logger.warning("Couldn't fetch users!")

                return None

            return [dict(zip(cursor.column_names, date)) for date in data]

    def sendOnlineNotification(self, member: Member, update: VoiceState):
        """
        Creates an online notification, but only for allowed channels and users who are opted-in

        :param member: Member that the users will be notified about
        :param update: VoiceStateUpdate
        :return:
        """
        logger.info("Creating Online-Notification for %s" % member.name)

        # if a channel does not count time
        if str(update.channel.id) not in ChannelIdWhatsAppAndTracking.getValues() and str(
                update.channel.id) not in ChannelIdUniversityTracking.getValues():
            return

        if member.bot:
            return

        triggerDcUserDb = getDiscordUser(self.databaseConnection, member)

        if not triggerDcUserDb:
            logger.warning("Couldn't fetch DiscordUser!")

            return

        if not self.__canSendMessage(triggerDcUserDb, WhatsAppParameter.WAIT_UNTIL_SEND_JOIN_AFTER_LEAVE.value):
            # delete leave message if user is fast enough back online
            if not self.__canSendMessage(triggerDcUserDb, WhatsAppParameter.WAIT_UNTIL_SEND_LEAVE.value):
                self.__retractMessagesFromMessageQueue(triggerDcUserDb, False)

            return

        if not (users := self.__getUsersForMessage()):
            return

        for user in users:
            # dont send message to trigger user
            if user['discord_user_id'] == triggerDcUserDb['id']:
                continue

            if triggerDcUserDb['channel_id'] in ChannelIdWhatsAppAndTracking.getValues() and user[
                'receive_join_notification']:
                # works correctly
                self.__queueWhatsAppMessage(triggerDcUserDb, update.channel, user, member.name)
            elif triggerDcUserDb['channel_id'] in ChannelIdUniversityTracking.getValues() and user[
                'receive_uni_join_notification']:
                self.__queueWhatsAppMessage(triggerDcUserDb, update.channel, user, member.name)

    def sendOfflineNotification(self, dcUserDb: dict, update: VoiceState, member: Member):
        """
        Creates an offline notification, but only for allowed channels and users who are opted-in

        :param dcUserDb: DiscordUser that caused the notification
        :param update: VoiceStateUpdate
        :param member: Member that caused the notification
        :return:
        """
        logger.info("Creating Offline-Notification for %s" % member.name)

        if lastOnline := dcUserDb['joined_at']:
            diff: timedelta = datetime.now() - lastOnline

            if diff.days <= 0:
                if diff.seconds <= WhatsAppParameter.WAIT_UNTIL_SEND_LEAVE.value * 60:
                    self.__retractMessagesFromMessageQueue(dcUserDb, True)

                    return

        if not self.__canSendMessage(dcUserDb, WhatsAppParameter.SEND_LEAVE_AFTER_X_MINUTES_AFTER_LAST_ONLINE.value):
            return

        if not (users := self.__getUsersForMessage()):
            return

        for user in users:
            if user['discord_user_id'] == dcUserDb['id']:
                continue

            # use a channel id here, dcUserDb no longer holds a channel id in this method
            if str(update.channel.id) in ChannelIdWhatsAppAndTracking.getValues() and user[
                'receive_leave_notification']:
                self.__queueWhatsAppMessage(dcUserDb, None, user, member.name)
            elif str(update.channel.id) in ChannelIdUniversityTracking.getValues() and user[
                'receive_uni_leave_notification']:
                self.__queueWhatsAppMessage(dcUserDb, None, user, member.name)

    def switchChannelFromOutstandingMessages(self, dcUserDb: dict, channelName: string):
        """
        If a DiscordUser switches channel within a timeinterval the unsent message will be edited

        :param dcUserDb: DiscordUser, who changed the channels
        :param channelName: New Channel
        :return:
        """
        logger.info("Editing message from %s caused by changing channels" % dcUserDb['username'])

        if (messages := getUnsendMessagesFromTriggerUser(self.databaseConnection, dcUserDb, True)) is None:
            return

        if len(messages) == 0:
            return

        with self.databaseConnection.cursor() as cursor:
            for message in messages:
                message['message'] = dcUserDb['username'] + " ist nun im Channel " + channelName + "."

                query, nones = WriteSaveQuery.writeSaveQuery(
                    'message_queue',
                    message['id'],
                    message
                )

                cursor.execute(query, nones)

            self.databaseConnection.commit()

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
        logger.info("Retracting messages from Queue for %s" % dcUserDb['username'])

        with self.databaseConnection.cursor() as cursor:
            messages = getUnsendMessagesFromTriggerUser(self.databaseConnection, dcUserDb, isJoinMessage)

            if messages is None:
                return

            for message in messages:
                query = "DELETE FROM message_queue WHERE id = %s"

                cursor.execute(query, (message['id'],))

            self.databaseConnection.commit()

    def __queueWhatsAppMessage(self, triggerDcUserDb: dict, channel, whatsappSetting: dict,
                               usernameFromTriggerUser: string):
        """
        Saves the message into the queue

        :param triggerDcUserDb: Trigger of the notification
        :param channel: Channel the user joined into
        :param whatsappSetting: User to send the message to
        :param usernameFromTriggerUser: Who triggered the message
        :return:
        """
        logger.info("Queueing message into database")

        with self.databaseConnection.cursor() as cursor:
            query = "SELECT channel_id FROM discord WHERE id = %s"

            cursor.execute(query, (whatsappSetting['discord_user_id'],))

            data = cursor.fetchone()

            if data is None:
                logger.warning("Couldn't fetch DiscordUser!")

                return

            dcUserDbRecipient = dict(zip(cursor.column_names, data))

            if dcUserDbRecipient['channel_id'] == triggerDcUserDb['channel_id']:
                return

            delay = WhatsAppParameter.DELAY_JOIN_MESSAGE.value
            timeToSent = datetime.now() + timedelta(minutes=delay)

            if not channel:
                joinMessages: list = getUnsendMessagesFromTriggerUser(self.databaseConnection, triggerDcUserDb, True)

                # if there are no join message send leave
                if joinMessages is None or len(joinMessages) == 0:
                    text = triggerDcUserDb[
                               'username'] + " (" + usernameFromTriggerUser + ") hat seinen Channel verlassen."
                    isJoinMessage = False
                # if there is a join message, delete them and don't send leave
                else:
                    self.__retractMessagesFromMessageQueue(triggerDcUserDb, True)

                    return
            else:
                text = triggerDcUserDb[
                           'username'] + " (" + usernameFromTriggerUser + ") ist nun um Channel " + channel.name + "."
                isJoinMessage = True

            query = "INSERT INTO message_queue (" \
                    "message, user_id, created_at, time_to_sent, trigger_user_id, is_join_message" \
                    ") VALUES (%s, %s, %s, %s, %s, %s)"

            cursor.execute(query, (
                text, whatsappSetting['id'], datetime.now(), timeToSent, triggerDcUserDb['id'], isJoinMessage))
            self.databaseConnection.commit()

    def manageSuspendSetting(self, member: Member, start: str, end: str):
        """
        Enables a given time interval for the member to not receive messages in

        :param member: Member, who requested the interval
        :param start: Starttime
        :param end: Endtime
        :return:
        """
        with self.databaseConnection.cursor() as cursor:
            query = "SELECT * FROM whatsapp_setting WHERE discord_user_id = (SELECT id FROM discord WHERE user_id = %s)"

            cursor.execute(query, (member.id,))

            data = cursor.fetchone()

            if not data:
                return "Du bist nicht für unseren WhatsApp-Nachrichtendienst registriert!"

            data = dict(zip(cursor.column_names, data))

        current = datetime.now()

        try:
            startTime: datetime = datetime.strptime(start, "%H:%M")
            startTime = startTime.replace(year=current.year, month=current.month, day=current.day)
        except ValueError:
            return "Bitte wähle eine korrekte Startzeit aus!"

        try:
            endTime: datetime = datetime.strptime(end, "%H:%M")
            endTime = endTime.replace(year=current.year, month=current.month, day=current.day)
        except ValueError:
            return "Bitte wähle eine korrekt Endzeit aus!"

        data['suspend_start'] = startTime
        data['suspend_end'] = endTime

        with self.databaseConnection.cursor() as cursor:
            query, nones = WriteSaveQuery.writeSaveQuery(
                'whatsapp_setting',
                data['id'],
                data,
            )

            cursor.execute(query, nones)
            self.databaseConnection.commit()

        return "Du bekommst von nun an ab %s bis %s keine WhatsApp-Nachrichten mehr." % (
            startTime.strftime("%H:%M"), endTime.strftime("%H:%M"))

    def resetSuspendSetting(self, member: Member):
        """
        Resets the suspend settings to None

        :param member: Member, who wishes to have his / her settings revoked
        :return:
        """
        with self.databaseConnection.cursor() as cursor:
            query = "SELECT * FROM whatsapp_setting WHERE discord_user_id = (SELECT id FROM discord WHERE user_id = %s)"

            cursor.execute(query, (member.id,))

            data = cursor.fetchone()

            if not data:
                return "Du bist nicht für unseren WhatsApp-Nachrichtendienst registriert!"

            data = dict(zip(cursor.column_names, data))
            data['suspend_start'] = None
            data['suspend_end'] = None

            query, nones = WriteSaveQuery.writeSaveQuery(
                'whatsapp_setting',
                data['id'],
                data,
            )

            cursor.execute(query, nones)
            self.databaseConnection.commit()

            return "Du bekommst nun wieder durchgehend WhatsApp-Nachrichten."

    def __del__(self):
        self.databaseConnection.close()
