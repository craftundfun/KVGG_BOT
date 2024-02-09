import logging
from datetime import datetime
from enum import Enum

import discord.ui

from src.Id.GuildId import GuildId

logger = logging.getLogger("API")


class PaginationViewDataTypes(Enum):
    TEXT = "str"
    PICTURE = "url"


class PaginationViewDataItem:
    field_name: str
    field_value: str
    data_type: PaginationViewDataTypes

    def __init__(self, field_name: str, data_type: PaginationViewDataTypes, field_value: str = ""):
        self.field_name = field_name
        self.data_type = data_type
        self.field_value = field_value


class PaginationView:
    current_page: int = 1
    seperator: int = 15

    def __init__(self, ctx: discord.Interaction, data: list[PaginationViewDataItem], client: discord.Client, defer=True,
                 seperator=15, title=""):
        self.seperator = seperator
        self.title = title
        self.member = ctx.user
        self.data = data
        self.ctx = ctx
        self.view = discord.ui.View(timeout=20.0)
        self.client = client
        self.last_page = int(len(self.data) / self.seperator) + 1
        self.is_paginated = len(self.data) > self.seperator
        self.defer = defer

    async def send(self):
        """
        Sends a pagination view message to the channel.
        """
        if self.defer:
            await self.ctx.response.defer(thinking=True)

        def update_button():
            """Update Button States based on the curren Page"""
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
                """
                Update message view when a timeout occurs.

                This method is called when a timeout occurs in the UI. It fetches the message from the specified guild
                and channel, clears the items in the view, and updates the message with the updated view.
                """
                message = await (self.client.get_guild(GuildId.GUILD_KVGG.value)
                                 .get_channel(self.message.channel.id)
                                 .fetch_message(self.message.id))

                self.view.clear_items()

                await message.edit(view=self.view)

            self.view.on_timeout = on_timeout_callback

            update_button()

        async def update_message(data: list[PaginationViewDataItem], interaction: discord.Interaction):
            """
            Updates the message with the provided data and interaction.

            :param data: (list[PaginationViewDataItem]): The list of data items to update the message with.
            :interaction: (discord.Interaction): The interaction object representing the user's interaction.

            """
            update_button()

            await interaction.response.edit_message(embed=self.create_embed(data), view=self.view)

        self.message = await self.ctx.followup.send(embed=self.create_embed(self.data[0:self.seperator]),
                                                    view=self.view, wait=True)

    def create_embed(self, data: list[PaginationViewDataItem]) -> discord.Embed:
        """
        Create an embed with the given data.

        :param data: A list of PaginationViewDataItem objects containing the field name and value.

        :returns: An instance of discord.Embed containing the created embed.
        """
        embed = discord.Embed(title=self.title, color=discord.Color.dark_blue())
        embed.set_author(name=self.member.name, icon_url=self.member.avatar.url)
        embed.timestamp = datetime.now()

        if self.is_paginated:
            embed.set_footer(text=f"KVGG • Seite {self.current_page} | {self.last_page}")
        else:
            embed.set_footer(text=f"KVGG")

        for item in data:
            match item.data_type:
                case PaginationViewDataTypes.TEXT:
                    embed.add_field(name=item.field_name, value=item.field_value)
                case PaginationViewDataTypes.PICTURE:
                    embed.set_image(url=item.field_value)
                case _:
                    logger.error("unknown item type encountered")

        return embed
