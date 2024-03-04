import logging
from datetime import datetime
from pathlib import Path

import discord
from discord import Client
from discord import Member

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.DiscordParameters.StatisticsParameter import StatisticsParameter
from src.Helper.GetFormattedTime import getFormattedTime
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Manager.AchievementManager import AchievementService
from src.Manager.StatisticManager import StatisticManager
from src.Repository.DiscordGameRepository import getGameDiscordRelation
from src.Services.Database import Database
from src.Services.QuestService import QuestService, QuestType

logger = logging.getLogger("KVGG_BOT")


class GameDiscordService:
    basepath = Path(__file__).parent.parent.parent

    def __init__(self, client: Client):
        self.client = client

        self.questService = QuestService(self.client)
        self.statisticManager = StatisticManager(self.client)
        self.achievementService = AchievementService(self.client)

    async def increaseGameRelationsForMember(self, member: Member, database: Database):
        """
        Increases the value of all current activities from the given member.

        :param member: The member to increase the values
        :param database:
        """
        now = datetime.now()

        for activity in member.activities:
            if isinstance(activity, discord.CustomActivity):
                logger.debug(f"{member.display_name} had an custom activity: {activity.name} => dont count it")

                continue
            elif isinstance(activity, discord.Streaming):
                logger.debug(f"{member.display_name} had an custom streaming-activity: "
                             f"{activity.name} => dont count it")

                continue

            if relation := getGameDiscordRelation(database, member, activity.name):
                if member.voice:
                    relation['time_played_online'] += 1

                    await self.questService.addProgressToQuest(member, QuestType.ACTIVITY_TIME)
                    self.statisticManager.increaseStatistic(StatisticsParameter.ACTIVITY, member)

                    if (relation['time_played_online'] % (AchievementParameter.TIME_PLAYED_HOURS.value * 60)) == 0:
                        await self.achievementService.sendAchievementAndGrantBoost(member,
                                                                                   AchievementParameter.TIME_PLAYED,
                                                                                   relation['time_played_online'])
                else:
                    relation['time_played_offline'] += 1

                relation['last_played'] = now
                saveQuery, nones = writeSaveQuery("game_discord_mapping", relation['id'], relation)

                if not database.runQueryOnDatabase(saveQuery, nones):
                    logger.error(f"couldn't increase activity value for {member.display_name} and "
                                 f"{activity.name}")

                    continue

                logger.debug(f"increased {activity.name} for {member.display_name}")
            else:
                logger.warning("couldn't fetch game_discord_relation, continuing")

                continue

    def getMostPlayedGames(self, limit: int = 3) -> list[dict] | None:
        database = Database()
        query = ("SELECT dg.name, SUM(gdm.time_played_online) + SUM(gdm.time_played_offline) AS time_played "
                 "FROM discord_game dg JOIN game_discord_mapping gdm ON dg.id = gdm.discord_game_id "
                 "GROUP BY gdm.discord_game_id "
                 "ORDER BY time_played DESC "
                 "LIMIT %s")

        if not (games := database.fetchAllResults(query, (limit,))):
            logger.error("couldn't fetch any most played games from the database")

            return None

        logger.debug("fetched most played games")

        return games

    def getMostPlayedGamesForLeaderboard(self, limit: int = 3) -> str:
        """
        Returns the most played games sorted by time_played and returns a string to use it in the leaderboard

        :param limit: Optional limit to receive more than three results
        """
        answer = ""
        games = self.getMostPlayedGames(limit)

        if not games:
            return "Es gab einen Fehler!"

        for index, game in enumerate(games, 1):
            answer += f"\t{index}: {game['name']} - {getFormattedTime(game['time_played'])} Stunden\n"

        answer += ("\n`Diese Stunden sind zusammengerechnet über alle User. Außerdem können die Zahlen evtl. nicht "
                   "mit der Wirklichkeit übereinstimmen => Limitation von Discord.`")

        return answer
