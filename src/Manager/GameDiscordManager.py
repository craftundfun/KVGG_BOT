import logging

import discord
from discord import Member

from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Repository.DiscordGameRepository import getGameDiscordRelation
from src.Services.Database import Database

logger = logging.getLogger("KVGG_BOT")


class GameDiscordManager:

    def __init__(self):
        pass

    def increaseGameRelationsForMember(self, member: Member, database: Database):
        """
        Increases the value of all current activities from the given member.

        :param member: The member to increase the values
        :param database:
        """
        for activity in member.activities:
            if not isinstance(activity, discord.Activity):
                logger.debug("activity type is not a discord.Activity instance")

                continue

            if relation := getGameDiscordRelation(database, member, activity):
                relation['time_played'] += 1
                saveQuery, nones = writeSaveQuery("game_discord_mapping", relation['id'], relation)

                if not database.runQueryOnDatabase(saveQuery, nones):
                    logger.error(f"couldn't increase activity value for {member.display_name} and "
                                 f"{activity.name}")

                    continue

                logger.debug(f"increased {activity.name} for {member.display_name}")
            else:
                logger.warning("couldn't fetch game_discord_relation, continuing")

                continue
