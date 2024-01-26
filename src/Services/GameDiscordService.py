import logging

import discord
from discord import Member

from src.Helper.GetFormattedTime import getFormattedTime
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Repository.DiscordGameRepository import getGameDiscordRelation
from src.Services.Database import Database

logger = logging.getLogger("KVGG_BOT")


class GameDiscordService:

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

    def getMostPlayedGamesForLeaderboard(self, limit: int = 3) -> str:
        """
        Returns the most played games sorted by time_played and returns a string to use it in the leaderboard

        :param limit: Optional limit to receive more than three results
        """
        database = Database()
        answer = ""
        query = ("SELECT dg.name, SUM(gdm.time_played) AS time_played "
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

        return answer
