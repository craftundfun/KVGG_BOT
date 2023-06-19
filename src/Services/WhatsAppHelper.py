from __future__ import annotations

import string

from datetime import datetime, timedelta
from discord import VoiceState, Member
from src.DiscordParameters.WhatsAppParameter import WhatsAppParameter
from src.Helper import WriteSaveQuery
from src.Id.ChannelIdWhatsAppAndTracking import ChannelIdWhatsAppAndTracking
from src.Id.ChannelIdUniversityTracking import ChannelIdUniversityTracking
from src.Repository.DiscordUserRepository import getDiscordUser
from src.Repository.MessageQueueRepository import getUnsendMessagesFromTriggerUser
from src.Helper.createNewDatabaseConnection import getDatabaseConnection


class WhatsAppHelper:
    def __init__(self):
        self.databaseConnection = getDatabaseConnection()

    def sendOnlineNotification(self, member: Member, update: VoiceState):
        # if a channel does not count time
        if str(update.channel.id) not in ChannelIdWhatsAppAndTracking.getValues() and str(
                update.channel.id) not in ChannelIdUniversityTracking.getValues():
            return

        if member.bot:
            return

        dcUserDb = getDiscordUser(self.databaseConnection, member)

        if not dcUserDb:
            return

        if not self.__canSendMessage(dcUserDb, WhatsAppParameter.WAIT_UNTIL_SEND_JOIN_AFTER_LEAVE.value):
            # delete leave message if user is fast enough back online
            if not self.__canSendMessage(dcUserDb, WhatsAppParameter.WAIT_UNTIL_SEND_LEAVE.value):
                self.__retractMessagesFromMessageQueue(dcUserDb, False)

            return

        with self.databaseConnection.cursor() as cursor:
            query = "SELECT * FROM user WHERE phone_number IS NOT NULL and api_key_whats_app IS NOT NULL"

            cursor.execute(query)

            data = cursor.fetchall()

            if data is None:
                return

            users = [dict(zip(cursor.column_names, date)) for date in data]

        for user in users:
            # dont send message to trigger user
            if user['discord_user_id'] == dcUserDb['id']:
                continue

            if dcUserDb['channel_id'] in ChannelIdWhatsAppAndTracking.getValues() and user[
                'recieve_join_notification']:
                # works correctly
                self.__queueWhatsAppMessage(dcUserDb, update.channel, user)
            elif dcUserDb['channel_id'] in ChannelIdUniversityTracking.getValues() and user[
                'receive_uni_join_notification']:
                self.__queueWhatsAppMessage(dcUserDb, update.channel, user)

    def sendOfflineNotification(self, dcUserDb: dict, update: VoiceState):
        with self.databaseConnection.cursor() as cursor:
            query = "SELECT * FROM user WHERE phone_number IS NOT NULL and api_key_whats_app IS NOT NULL"

            cursor.execute(query)

            data = cursor.fetchall()

            if not data:
                return

            users = [dict(zip(cursor.column_names, date)) for date in data]

        for user in users:
            if user['discord_user_id'] == dcUserDb['id']:
                continue

            # use a channel id here, dcUserDb no longer holds a channel id in this method
            if str(update.channel.id) in ChannelIdWhatsAppAndTracking.getValues() and user[
                'recieve_join_notification']:
                self.__queueWhatsAppMessage(dcUserDb, None, user)
            elif str(update.channel.id) in ChannelIdUniversityTracking.getValues() and user[
                'receive_uni_join_notification']:
                self.__queueWhatsAppMessage(dcUserDb, None, user)

    def switchChannelFromOutstandingMessages(self, dcUserDb: dict, channelName: string):
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
        if value := dcUserDb['last_online']:
            now = datetime.now()
            diff: timedelta = value - now

            if diff.days > 0 or diff.seconds > intervalTime * 60:
                return False
        return True

    def __retractMessagesFromMessageQueue(self, dcUserDb: dict, isJoinMessage: bool):
        with self.databaseConnection.cursor() as cursor:
            messages = getUnsendMessagesFromTriggerUser(self.databaseConnection, dcUserDb, isJoinMessage)

            if messages is None:
                return

            for message in messages:
                query = "DELETE FROM message_queue WHERE id = %s"

                cursor.execute(query, (message['id'],))

            self.databaseConnection.commit()

    def __queueWhatsAppMessage(self, triggerDcUserDb: dict, channel, user: dict):
        with self.databaseConnection.cursor() as cursor:
            query = "SELECT * FROM discord WHERE id = %s"

            cursor.execute(query, (user['discord_user_id'],))

            data = cursor.fetchone()

            if data is None:
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
                    text = triggerDcUserDb['username'] + " hat seinen Channel verlassen."
                    isJoinMessage = False
                # if there is a join message, delete them and don't send leave
                else:
                    self.__retractMessagesFromMessageQueue(triggerDcUserDb, True)

                    return
            else:
                text = triggerDcUserDb['username'] + " ist nun um Channel " + channel.name + "."
                isJoinMessage = True

            query = "INSERT INTO message_queue (" \
                    "message, user_id, created_at, time_to_sent, trigger_user_id, is_join_message" \
                    ") VALUES (%s, %s, %s, %s, %s, %s)"

            cursor.execute(query, (text, user['id'], datetime.now(), timeToSent, triggerDcUserDb['id'], isJoinMessage))
            self.databaseConnection.commit()

    def __del__(self):
        self.databaseConnection.close()
