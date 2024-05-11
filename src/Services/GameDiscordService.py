import logging
from datetime import datetime
from pathlib import Path

import discord
from discord import Client
from discord import Member
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.DiscordParameters.StatisticsParameter import StatisticsParameter
from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Entities.Game.Entity.DiscordGame import DiscordGame
from src.Entities.Game.Entity.GameDiscordMapping import GameDiscordMapping
from src.Entities.Game.Repository.DiscordGameRepository import getGameDiscordRelation
from src.Helper.GetFormattedTime import getFormattedTime
from src.Manager.AchievementManager import AchievementService
from src.Manager.DatabaseManager import getSession
from src.Manager.StatisticManager import StatisticManager
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
        canIncreaseStatistic = False
        # noinspection PyTypeChecker
        getQuery = (select(GameDiscordMapping)
                    .where(GameDiscordMapping.discord_id == (select(DiscordUser.id)
                                                             .where(DiscordUser.user_id == str(member.id))
                                                             .scalar_subquery()),
                           GameDiscordMapping.currently_playing == True, ))

        try:
            activeRelations = session.scalars(getQuery).all()
        except Exception as error:
            logger.error(f"couldn't fetch active relations for {member.display_name}", exc_info=error)

            return
        else:
            # empty all active relations
            if activeRelations:
                for relation in activeRelations:
                    relation.currently_playing = False

                try:
                    session.commit()
                except Exception as error:
                    logger.error(f"couldn't update active relations for {member.display_name}", exc_info=error)
                    session.rollback()
                    session.close()

                    return
                else:
                    logger.debug(f"reset {len(activeRelations)} active relations for {member.display_name}")
            else:
                logger.debug(f"no relations found for reset active relations for {member.display_name}")

            try:
                session.commit()
            except Exception as error:
                logger.error(f"couldn't update active relations for {member.display_name}", exc_info=error)
                session.rollback()
                session.close()

                return

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

                    if (relation.time_played_online % (AchievementParameter.TIME_PLAYED_HOURS.value * 60)) == 0:
                        await self.achievementService.sendAchievementAndGrantBoost(member,
                                                                                   AchievementParameter.TIME_PLAYED,
                                                                                   relation.time_played_online,
                                                                                   gameName=relation.discord_game.name, )
                else:
                    relation.time_played_offline += 1

                relation.last_played = now
                canIncreaseStatistic = True
                relation.currently_playing = True

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

        if canIncreaseStatistic:
            self.statisticManager.increaseStatistic(StatisticsParameter.ACTIVITY, member, session)
            logger.debug(f"increased activity statistics for {member.display_name}")

    # noinspection PyMethodMayBeStatic
    def getOverallPlayedTime(self, member: Member, dcUserDb: DiscordUser, session: Session) -> str | None:
        """
        Returns the overall played time of the given member

        :param member: The member to get the overall played time
        :param dcUserDb: DiscordUser of the given member
        :param session: The session for the database
        """
        try:
            result = session.query(text("SUM(time_played_online) + SUM(time_played_offline) "
                                        "FROM game_discord_mapping "
                                        "WHERE discord_id = :id")).params(id=dcUserDb.id)
        except Exception as error:
            logger.error(f"couldn't get overall played time for {member.display_name}", exc_info=error)

            return None

        return getFormattedTime(result[0][0])

    # noinspection PyMethodMayBeStatic
    def chooseRandomGame(self, members: [Member]) -> str:
        """
        Chooses a random game that both members have played together
        """
        if not (session := getSession()):
            return "Es gab einen Fehler!"

        # the SELECT is *not* missing here: writing it results in a syntax error
        baseQuery = ("DISTINCT gdm1.discord_game_id "
                     "FROM game_discord_mapping AS gdm1 ")

        # generate the join and where clauses for each member
        joinClauses = []
        whereClauses = []

        for i, member in enumerate(members[1:], start=1):
            joinClauses.append(f"JOIN game_discord_mapping AS gdm{i + 1} "
                               f"ON gdm1.discord_game_id = gdm{i + 1}.discord_game_id ")
            whereClauses.append(f"(gdm1.discord_id <> gdm{i + 1}.discord_id "
                                f"AND gdm{i + 1}.discord_id = (SELECT id FROM discord WHERE user_id = :user_id_{i})) ")

        # combine the base query, join clauses, and where clauses
        query = baseQuery + ''.join(joinClauses) + "WHERE " + ' AND '.join(whereClauses) + " ORDER BY RAND()"
        getQuery = text(query)

        try:
            # noinspection PyTypeChecker
            result: list[tuple[int]] = (session
                                        .query(getQuery)
                                        .params(**{f'user_id_{i}': str(member.id)
                                                   for i, member in enumerate(members, start=1)}, )
                                        .all())
        except Exception as error:
            logger.error(f"couldn't fetch random game for {members}",
                         exc_info=error)
            session.close()

            return "Es gab einen Fehler!"

        if not result:
            logger.debug(f"no game found for {members}")
            session.close()

            return (f"Ihr {'beide' if len(members) == 2 else ('drei' if len(members) == 3 else 'vier')} "
                    f"habt keine gemeinsamen Spiele gespielt.")
        else:
            logger.debug(f"fetched random game for {members} with ID: {result[0][0]}")

        print(result)

        # noinspection PyTypeChecker
        getQuery = select(DiscordGame).where(DiscordGame.id == result[0][0])

        try:
            game = session.scalars(getQuery).one()
        except Exception as error:
            logger.error(f"couldn't fetch game with ID: {result[0][0]}", exc_info=error)
            session.close()

            return "Es gab einen Fehler!"

        answer = (f"Das zufällig ausgewählte Spiel (oder Programm) aus eurer "
                  f"({', '.join(member.display_name for member in members)})"
                  f" Sammlung ist:\n\n**__{game.name}__**\n\n"
                  f"`Es kann sein, dass das Spiel kein wirkliches Spiel ist. Das liegt aber nicht an uns, sondern "
                  f"an Discord.`")

        session.close()

        return answer
