import logging

import discord
from discord import Client
from discord import Member

from src.Helper.GetFormattedTime import getFormattedTime
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Repository.DiscordGameRepository import getGameDiscordRelation
from src.Repository.DiscordUserRepository import getDiscordUser
from src.Services.Database import Database

logger = logging.getLogger("KVGG_BOT")


class GameDiscordService:

    def __init__(self, client: Client):
        self.client = client

    def increaseGameRelationsForMember(self, member: Member, database: Database):
        """
        Increases the value of all current activities from the given member.

        :param member: The member to increase the values
        :param database:
        """
        for activity in member.activities:
            if isinstance(activity, discord.CustomActivity):
                logger.debug(f"{member.display_name} had an custom activity: {activity.name} => dont count it")

                continue
            elif isinstance(activity, discord.Streaming):
                logger.debug(f"{member.display_name} had an custom streaming-activity: "
                             f"{activity.name} => dont count it")

                continue

            if relation := getGameDiscordRelation(database,
                                                  member,
                                                  activity if isinstance(activity, discord.Activity) else None,
                                                  activity.name):
                if member.voice:
                    relation['time_played_online'] += 1
                else:
                    relation['time_played_offline'] += 1

                saveQuery, nones = writeSaveQuery("game_discord_mapping", relation['id'], relation)

                if not database.runQueryOnDatabase(saveQuery, nones):
                    logger.error(f"couldn't increase activity value for {member.display_name} and "
                                 f"{activity.name}")

                    continue

                logger.debug(f"increased {activity.name} for {member.display_name}")
            else:
                logger.warning("couldn't fetch game_discord_relation, continuing")

                continue

    def getMostPlayedGamesForLeaderboard(self, limit: int = 3) -> str:
        """
        Returns the most played games sorted by time_played and returns a string to use it in the leaderboard

        :param limit: Optional limit to receive more than three results
        """
        database = Database()
        answer = ""
        query = ("SELECT dg.name, SUM(gdm.time_played_online) + SUM(gdm.time_played_offline) AS time_played "
                 "FROM discord_game dg JOIN game_discord_mapping gdm ON dg.id = gdm.discord_game_id "
                 "GROUP BY gdm.discord_game_id "
                 "ORDER BY time_played DESC "
                 "LIMIT %s")

        if not (games := database.fetchAllResults(query, (limit,))):
            logger.error("couldn't fetch any most played games from the database")

            return "Es gab einen Fehler"

        logger.debug("fetched most played games")

        for index, game in enumerate(games, 1):
            answer += f"\t{index}: {game['name']} - {getFormattedTime(game['time_played'])} Stunden\n"

        answer += ("\n`Diese Stunden sind zusammengerechnet über alle User. Außerdem können die Zahlen evtl. nicht "
                   "mit der Wirklichkeit übereinstimmen => Limitation von Discord.`")

        return answer

    async def runIncreaseGameRelationForEveryone(self):
        database = Database()

        for member in self.client.get_all_members():
            if getDiscordUser(member, database):
                self.increaseGameRelationsForMember(member, database)
