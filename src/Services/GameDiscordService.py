import logging
from datetime import datetime
from pathlib import Path

import discord
from discord import Client
from discord import Member
from sqlalchemy.orm import Session

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.DiscordParameters.StatisticsParameter import StatisticsParameter
from src.Manager.AchievementManager import AchievementService
from src.Manager.StatisticManager import StatisticManager
from src.Repository.Game.Repository.DiscordGameRepository import getGameDiscordRelation
from src.Services.QuestService import QuestService, QuestType

logger = logging.getLogger("KVGG_BOT")


class GameDiscordService:
    basepath = Path(__file__).parent.parent.parent

    def __init__(self, client: Client):
        self.client = client

        self.questService = QuestService(self.client)
        self.statisticManager = StatisticManager(self.client)
        self.achievementService = AchievementService(self.client)

    async def increaseGameRelationsForMember(self, member: Member, session: Session):
        """
        Increases the value of all current activities from the given member.

        :param member: The member to increase the values
        :param session:
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

            if relation := getGameDiscordRelation(session, member, activity.name):
                if member.voice:
                    relation.time_played_online += 1

                    await self.questService.addProgressToQuest(member, QuestType.ACTIVITY_TIME)
                    self.statisticManager.increaseStatistic(StatisticsParameter.ACTIVITY, member)

                    if (relation.time_played_online % (AchievementParameter.TIME_PLAYED_HOURS.value * 60)) == 0:
                        await self.achievementService.sendAchievementAndGrantBoost(member,
                                                                                   AchievementParameter.TIME_PLAYED,
                                                                                   relation.time_played_online,
                                                                                   gameName=relation.discord_game.name, )
                else:
                    relation.time_played_offline += 1

                relation.last_played = now

                try:
                    session.commit()
                except Exception as error:
                    logger.error(f"couldn't save GameDiscordMapping for {member.display_name} and {activity.name}",
                                 exc_info=error, )
                    session.rollback()

                    continue
                else:
                    logger.debug(f"increased {activity.name} for {member.display_name}")
            else:
                logger.error("couldn't fetch game_discord_relation, continuing")

                continue
