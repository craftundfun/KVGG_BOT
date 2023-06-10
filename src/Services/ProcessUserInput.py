from discord import Message, Client
import mysql.connector
from src.Helper import ReadParameters as rp
from src.Helper.ReadParameters import Parameters as parameters
from src.Id import ChannelId


class ProcessUserInput:
    cnx = None

    def __init__(self):
        self.cnx = mysql.connector.connect(
            user=rp.getParameter(parameters.USER),
            password=rp.getParameter(parameters.PASSWORD),
            host=rp.getParameter(parameters.HOST),
            database=rp.getParameter(parameters.NAME),
        )

    def processMessage(self, message: Message, client: Client):
        if message.channel.guild.id is None or message.author.id is None:
            return

        cursor = self.cnx.cursor()
        query = "SELECT * FROM discord WHERE user_id = %s"

        cursor.execute(query, ([message.author.id]))
        dcUserDb = cursor.fetchmany(1)[0]
        print(cursor.column_names)
        if not dcUserDb:
            pass  # TODO create DiscordUser

        dcUserDb = dict(zip(cursor.column_names, dcUserDb))
        print(dcUserDb)
        # if message.channel.id != ChannelId.ChannelId.CHANNEL_BOT_TEST_ENVIRONMENT.value:
        dcUserDb['message_count_all_time'] = dcUserDb['message_count_all_time'] + 10210312
        print(dcUserDb)
