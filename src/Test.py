from asyncio import sleep
from threading import Thread

import discord


class Test(Thread):

    def __init__(self, client: discord.Client):
        super().__init__()
        self.client = client

    async def run(self):
        while True:
            print("Hey")
            await sleep(2)
