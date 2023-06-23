import logging
from datetime import datetime
from discord import Client, ChannelType
from src.Helper import WriteSaveQuery
from src.Helper.createNewDatabaseConnection import getDatabaseConnection

logger = logging.getLogger("KVGG_BOT")


class BotStartUpService:

    def __init__(self):
        self.databaseConnection = getDatabaseConnection()

    async def startUp(self, client: Client):
        """
        Brings the database up to the current state of the server

        :param client: Discord client
        :return:
        """
        logger.info("Beginning fetching data")
        with self.databaseConnection.cursor() as cursor:
            query = "SELECT * FROM discord"

            cursor.execute(query)

            data = cursor.fetchall()

            if not data:
                return

            dcUsersDb = [dict(zip(cursor.column_names, date)) for date in data]

        # for every user
        for user in dcUsersDb:
            foundInChannel = False
            # look in every channel
            for channel in client.get_all_channels():
                if foundInChannel:
                    break

                # filter out none voice channels
                if channel.type != ChannelType.voice:
                    continue

                members = channel.members

                # for every member in this voice channel
                for member in members:
                    # if the user was found, save the (new) channel id and break
                    if member.id == int(user['user_id']):
                        user['channel_id'] = channel.id
                        user['joined_at'] = datetime.now()
                        voiceState = channel.voice_states[member.id]

                        if voiceState.self_mute:
                            user['muted_at'] = datetime.now()
                        else:
                            user['muted_at'] = None

                        if voiceState.self_deaf:
                            user['full_muted_at'] = datetime.now()
                        else:
                            user['full_muted_at'] = None

                        if voiceState.self_stream:
                            user['started_stream_at'] = datetime.now()
                        else:
                            user['started_stream_at'] = None

                        if voiceState.self_video:
                            user['started_webcam_at'] = datetime.now()
                        else:
                            user['started_webcam_at'] = None

                        foundInChannel = True
                        break

            if not foundInChannel:
                # overwrite last online only if user was previously in a channel
                if user['channel_id']:
                    user['last_online'] = datetime.now()
                user['channel_id'] = None
                user['joined_at'] = None
                user['started_stream_at'] = None
                user['started_webcam_at'] = None
                user['muted_at'] = None
                user['full_muted_at'] = None

        with self.databaseConnection.cursor() as cursor:
            for user in dcUsersDb:
                query, nones = WriteSaveQuery.writeSaveQuery(
                    'discord',
                    user['id'],
                    user,
                )

                cursor.execute(query, nones)

        self.databaseConnection.commit()

    def __del__(self):
        self.databaseConnection.close()
