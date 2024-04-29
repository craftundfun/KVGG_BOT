import discord
from sqlalchemy import select, null

from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Helper import ReadParameters
from src.Id.GuildId import GuildId
from src.Manager.DatabaseManager import getSession


class MyClient(discord.Client):

    def __init__(self, *, intents, **options):
        super().__init__(intents=intents, **options)

    async def on_ready(self):
        if not (session := getSession()):
            print("[ERROR] couldn't fetch session")

            return

        getQuery = select(DiscordUser)

        try:
            dcUsersDb = session.scalars(getQuery).all()
        except Exception as error:
            print("[ERROR] couldn't fetch all users", error)

            return
        else:
            print(f"[INFO] fetched {len(dcUsersDb)} users")

        for dcUserDb in dcUsersDb:
            member = self.get_guild(GuildId.GUILD_KVGG.value).get_member(int(dcUserDb.user_id))

            if not member:
                print(f"[INFO] couldn't find member for {dcUserDb.username}")

                dcUserDb.guild_id = null()
            else:
                print(f"[INFO] found member for {dcUserDb.username}")

                continue

            try:
                session.commit()
            except Exception as error:
                print(f"[ERROR] couldn't update guild_id for {dcUserDb.username}", error)


if __name__ == '__main__':
    client = MyClient(intents=discord.Intents.all(), reconnect=True, )
    client.run(token=ReadParameters.getParameter(ReadParameters.Parameters.DISCORD_TOKEN))
