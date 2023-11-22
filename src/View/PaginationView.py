from datetime import datetime

import discord.ui

from src.Id.ChannelId import ChannelId
from src.Id.GuildId import GuildId

class PaginationViewDataItem:
    field_name: str
    field_value: str

    def __init__(self, field_name: str, field_value: str = ""):
        self.field_name = field_name
        self.field_value = field_value

class PaginationView:
    current_page : int = 1
    seperator : int = 15

    def __init__(self, ctx: discord.Interaction, data: list[PaginationViewDataItem], client: discord.Client, defer=True, seperator=15, title=""):
        self.seperator = seperator
        self.title = title
        self.member = ctx.user
        self.data = data
        self.ctx = ctx
        self.view = discord.ui.View(timeout=20.0)
        self.client = client
        self.last_page = int(len(self.data) / self.seperator) + 1
        self.is_paginated =  len(self.data) > self.seperator
        self.defer = defer


    async def send(self):

        if self.defer:
            await self.ctx.response.defer(thinking=True)

        def update_button():

            if self.current_page == 1:
                first_page_button.disabled = True
                previous_button.disabled = True
            else:
                first_page_button.disabled = False
                previous_button.disabled = False

            if self.current_page == len(self.data) // self.seperator + 1:
                next_button.disabled = True
                last_page_button.disabled = True
            else:
                next_button.disabled = False
                last_page_button.disabled = False

        if self.is_paginated:
            first_page_button = discord.ui.Button(label="|<", style=discord.ButtonStyle.green)
            async def first_page_button_callback(interaction: discord.Interaction):
                self.current_page = 1
                until_item = self.seperator
                await update_message(self.data[0:until_item], interaction=interaction)

            first_page_button.callback = first_page_button_callback

            previous_button = discord.ui.Button(label="<", style=discord.ButtonStyle.green)
            async def previous_button_callback(interaction: discord.Interaction):
                self.current_page -= 1
                until_item = self.current_page * self.seperator
                from_item = until_item - self.seperator
                await update_message(self.data[from_item:until_item], interaction=interaction)

            previous_button.callback = previous_button_callback

            next_button = discord.ui.Button(label=">", style=discord.ButtonStyle.green)
            async def next_button_callback(interaction: discord.Interaction):
                self.current_page += 1
                until_item = self.current_page * self.seperator
                from_item = until_item - self.seperator
                await update_message(self.data[from_item:until_item], interaction=interaction)

            next_button.callback = next_button_callback

            last_page_button = discord.ui.Button(label=">|", style=discord.ButtonStyle.green)
            async def last_page_button_callback(interaction: discord.Interaction):
                self.current_page = self.last_page
                until_item = self.last_page * self.seperator
                from_item = until_item - self.seperator
                await update_message(self.data[from_item:], interaction=interaction)

            last_page_button.callback = last_page_button_callback

            self.view.add_item(first_page_button)
            self.view.add_item(previous_button)
            self.view.add_item(next_button)
            self.view.add_item(last_page_button)

            async def on_timeout_callback():
                message = await (self.client.get_guild(GuildId.GUILD_KVGG.value)
                                 .get_channel(self.message.channel.id)
                                 .fetch_message(self.message.id))

                self.view.clear_items()

                await message.edit(view=self.view)

            self.view.on_timeout = on_timeout_callback

            update_button()

        async def update_message(data: list[PaginationViewDataItem], interaction: discord.Interaction):
            update_button()

            await interaction.response.edit_message(embed=self.create_embed(data), view=self.view)

        self.message = await self.ctx.followup.send(embed=self.create_embed(self.data[0:self.seperator]), view=self.view, wait=True)


    def create_embed(self, data: list[PaginationViewDataItem]):
        embed = discord.Embed(title=self.title, color=discord.Color.dark_blue())
        embed.set_author(name=self.member.name, icon_url=self.member.avatar.url)
        embed.timestamp = datetime.now()

        if self.is_paginated:
            embed.set_footer(text=f"KVGG • Seite {self.current_page} | {self.last_page}")
        else:
            embed.set_footer(text=f"KVGG")

        for item in data:
            embed.add_field(name=item.field_name, value=item.field_value)

        return embed

