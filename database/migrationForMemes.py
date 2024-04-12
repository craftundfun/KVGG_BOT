import sys
from datetime import datetime

import discord

from src.Helper import ReadParameters
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Id.ChannelId import ChannelId
from src.Id.GuildId import GuildId
from src.Services.Database import Database


class MyClient(discord.Client):

    def __init__(self, *, intents, **options):
        super().__init__(intents=intents, **options)

    async def on_ready(self):
        database = Database()
        query = "SELECT * FROM meme"

        if not (memes := database.fetchAllResults(query)):
            print("no memes were found in the database")
            exit(1)

        channel = self.get_guild(GuildId.GUILD_KVGG.value).get_channel(ChannelId.CHANNEL_MEMES.value)

        for meme in memes:
            print(f"[INFO] looking at {meme['id']}")

            try:
                message: discord.Message = await channel.fetch_message(meme['message_id'])
            except discord.NotFound:
                print(f"[INFO] {meme['id']} was not found")

                meme['deleted_at'] = datetime.now()
                meme['media_link'] = None
            except Exception as error:
                print(f"[ERROR] {meme['id']}", error)

                continue
            else:
                print(f"[INFO] {meme['id']} was found")

                if len(message.attachments) == 0:
                    print(f"[INFO] {meme['id']} has no media, treat as deleted")

                    meme['media_link'] = None
                    meme['deleted_at'] = datetime.now()
                else:
                    meme['media_link'] = message.attachments[0].url

                    if message.pinned:
                        print(f"[INFO] {meme['id']} was winner")

                        meme['winner'] = 1
            finally:
                query, nones = writeSaveQuery("meme", meme['id'], meme)

                if not database.runQueryOnDatabase(query, nones):
                    print(f"[ERROR] couldn't update meme {meme['id']} to database")
                else:
                    print(f"[INFO] updated {meme['id']}")

            print("\n-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_\n")

        sys.exit(0)


if __name__ == '__main__':
    client = MyClient(intents=discord.Intents.all(), reconnect=True, )
    client.run(token=ReadParameters.getParameter(ReadParameters.Parameters.TOKEN))
