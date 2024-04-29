import logging
from datetime import datetime
from typing import Sequence

from discord import Member, Client
from sqlalchemy import select, insert
from sqlalchemy.orm import Session

from src.DiscordParameters.StatisticsParameter import StatisticsParameter
from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Entities.Statistic.Entity.CurrentDiscordStatistic import CurrentDiscordStatistic
from src.Entities.Statistic.Entity.StatisticLog import StatisticLog
from src.Entities.Statistic.Repository.StatisticRepository import getCurrentStatisticsForUser
from src.Helper.GetFormattedTime import getFormattedTime
from src.Id.GuildId import GuildId
from src.Manager.NotificationManager import NotificationService

logger = logging.getLogger("KVGG_BOT")


class StatisticManager:

    def __init__(self, client: Client):
        self.client = client

        self.notificationService = NotificationService(self.client)

    # noinspection PyMethodMayBeStatic
    def saveStatisticsToStatisticLog(self, time: StatisticsParameter, session: Session):
        """
        Saves the statistics (currently only online statistic) to the statistic-log database.

        :param time: Time to add statistics to
        :param session: The session to use for the database
        """
        for type in StatisticsParameter.getTypeValues():
            # noinspection PyTypeChecker
            getQuery = select(CurrentDiscordStatistic).where(CurrentDiscordStatistic.statistic_time == time.value,
                                                             CurrentDiscordStatistic.statistic_type == type, )

            try:
                statistics: Sequence[CurrentDiscordStatistic] = session.scalars(getQuery).all()
            except Exception as error:
                logger.error(f"couldn't fetch statistics for type:{type} and time: {time}", exc_info=error)

                continue

            if not statistics:
                logger.error(f"couldn't fetch statistics for type:{type} and time: {time}")

                return

            for statistic in statistics:
                insertQuery = insert(StatisticLog).values(type=time.value,
                                                          statistic_type=type,
                                                          created_at=datetime.now(),
                                                          discord_user_id=(discordUserId := statistic.discord_id),
                                                          value=statistic.value, )

                try:
                    session.execute(insertQuery)
                except Exception as error:
                    logger.error(f"couldn't insert statistics for {statistic.discord_id}, type: {type} and time: "
                                 f"{time}", exc_info=error)

                    continue

                # reset value so we don't have to insert it again
                statistic.value = 0

                try:
                    session.commit()
                except Exception as error:
                    logger.error(f"couldn't commit statistics for {statistic.discord_id}, type: {type} and time: "
                                 f"{time}", exc_info=error)

                    continue

    # noinspection PyMethodMayBeStatic
    def increaseStatistic(self, type: StatisticsParameter, member: Member, session: Session, value: int = 1):
        """
        Increases the value of the given statistic in each time period.

        :param type: The type of the statistic
        :param member: The member whose statistic is increases
        :param value: The value to add, standard value of 1.
        :param session: The session to use for the database
        """
        logger.debug(f"increasing statistics for {member.display_name} and type {type.value}")

        statistics: list[CurrentDiscordStatistic] = getCurrentStatisticsForUser(type, member, session)

        if not statistics:
            logger.error(f"got no statistics for {member.display_name}, aborting to increase")

            return

        # increase daily, weekly, monthly and yearly
        for statistic in statistics:
            statistic.value += value

            if statistic.value < 0:
                logger.debug(f"{statistic.statistic_type} had value: {statistic.value}, correcting to 0")

                statistic.value = 0

        try:
            session.commit()
        except Exception as error:
            logger.error(f"couldn't commit increase of statistics for {member.display_name}", exc_info=error)

            return

    async def runRetrospectForUsers(self, time: StatisticsParameter, session: Session):
        """
        Creates a retrospect for all users who have statistics for the given time period.

        :param time: Time period to send the retrospect for
        :param session: The session to use for the database
        """
        getQuery = (select(DiscordUser)
                    .distinct()
                    .join(CurrentDiscordStatistic)
                    .where(CurrentDiscordStatistic.statistic_time == time.value))

        try:
            dcUsersDb: Sequence[DiscordUser] = session.scalars(getQuery).all()
        except Exception as error:
            logger.error("couldn't fetch all users from database to create retrospects", exc_info=error)

            return

        for dcUserDb in dcUsersDb:
            logger.debug(f"creating retrospect for {dcUserDb}")

            if not (member := self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(int(dcUserDb.user_id))):
                logger.warning(f"couldn't fetch member from guild for {dcUserDb}")

                continue

            def getCorrectTimePeriod() -> str:
                match time:
                    case StatisticsParameter.WEEKLY:
                        return "die letzte Woche"
                    case StatisticsParameter.MONTHLY:
                        return "für den letzten Monat"
                    case StatisticsParameter.YEARLY:
                        return "für das letzte Jahr"
                    case _:
                        logger.error(f"undefined enum entry was reached: {time}")

                        return "FEHLER"

            statistics: Sequence[CurrentDiscordStatistic | None] = dcUserDb.current_discord_statistics
            message = f"__**Hey {member.display_name}, hier ist dein Rückblick für {getCorrectTimePeriod()}!**__\n\n"
            # if there are no statistics, the message will not be sent
            modified = False
            # Define the order of the statistics
            order = {
                StatisticsParameter.ONLINE.value: 1,
                StatisticsParameter.STREAM.value: 2,
                StatisticsParameter.ACTIVITY.value: 3,
                StatisticsParameter.UNIVERSITY.value: 4,
                StatisticsParameter.MESSAGE.value: 5,
                StatisticsParameter.COMMAND.value: 6,
            }
            # Sort the statistics based on the defined order
            sorted_statistics = sorted(statistics, key=lambda s: order.get(s.statistic_type, float('inf')))

            for statistic in sorted_statistics:
                if statistic.statistic_time != time.value:
                    continue

                match statistic.statistic_type:
                    case StatisticsParameter.ONLINE.value:
                        if statistic.value > 0:
                            message += f"-\tDu warst {getFormattedTime(statistic.value)} Stunden online.\n"
                            modified = True
                    case StatisticsParameter.STREAM.value:
                        if statistic.value > 0:
                            message += f"-\tDu hast insgesamt {getFormattedTime(statistic.value)} Stunden gestreamt.\n"
                            modified = True
                    case StatisticsParameter.MESSAGE.value:
                        if statistic.value > 0:
                            message += f"-\tDu hast {statistic.value} Nachrichten verfasst.\n"
                            modified = True
                    case StatisticsParameter.COMMAND.value:
                        if statistic.value > 0:
                            message += f"-\tDu hast mich {statistic.value} Mal genutzt (aka. Commands genutzt).\n"
                            modified = True
                    case StatisticsParameter.ACTIVITY.value:
                        if statistic.value > 0:
                            message += (f"-\tDu hast {getFormattedTime(statistic.value)} Stunden gespielt oder "
                                        f"Programme genutzt.\n")
                            modified = True
                    case StatisticsParameter.UNIVERSITY.value:
                        if statistic.value > 0:
                            message += f"-\tDu hast {getFormattedTime(statistic.value)} Stunden studiert.\n"
                            modified = True
                    case _:
                        logger.error(f"undefined enum entry was reached: {statistic.statistic_type} for {dcUserDb}")

                        continue

            if modified:
                await self.notificationService.sendRetrospect(member, message.rstrip("\n"))
                logger.debug(f"sent retrospect to {member.display_name}")
            else:
                logger.debug(f"no statistics for {dcUserDb}")
