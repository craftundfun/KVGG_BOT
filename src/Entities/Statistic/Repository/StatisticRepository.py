import logging

from discord import Member
from sqlalchemy import select, insert
from sqlalchemy.orm import Session

from src.DiscordParameters.StatisticsParameter import StatisticsParameter
from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Entities.Statistic.Entity.CurrentDiscordStatistic import CurrentDiscordStatistic

logger = logging.getLogger("KVGG_BOT")


def getCurrentStatisticsForUser(type: StatisticsParameter,
                                member: Member,
                                session: Session) -> list[CurrentDiscordStatistic] | None:
    # noinspection PyTypeChecker
    getQuery = (select(CurrentDiscordStatistic)
                .where(CurrentDiscordStatistic.statistic_type == type.value,
                       CurrentDiscordStatistic.discord_id == (select(DiscordUser.id)
                                                              .where(DiscordUser.user_id == str(member.id))
                                                              .scalar_subquery())))

    try:
        statistics = session.scalars(getQuery).all()
    except Exception as error:
        logger.error(f"an error occurred while fetching statistics for {member.display_name}", exc_info=error)
        return None

    if not statistics:
        logger.debug(f"no current statistics found for {member.display_name}, creating new ones")

        if not _insertStatistic(type, StatisticsParameter.DAILY, member, session):
            return None

        if not _insertStatistic(type, StatisticsParameter.WEEKLY, member, session):
            return None

        if not _insertStatistic(type, StatisticsParameter.MONTHLY, member, session):
            return None

        if not _insertStatistic(type, StatisticsParameter.YEARLY, member, session):
            return None

        try:
            statistics = session.scalars(getQuery).all()
        except Exception as error:
            logger.error(f"couldn't fetch newly inserted current discord statistics for {member.display_name}",
                         exc_info=error, )
            return None

    if len(statistics) != 4:
        logger.debug("less then 3 statistics, searching missing one and creating it")

        times = [StatisticsParameter.DAILY.value,
                 StatisticsParameter.WEEKLY.value,
                 StatisticsParameter.MONTHLY.value,
                 StatisticsParameter.YEARLY.value, ]

        for stat in list(statistics):
            if stat.statistic_time in times:
                times.remove(stat.statistic_time)

        if StatisticsParameter.DAILY.value in times:
            if not _insertStatistic(type, StatisticsParameter.DAILY, member, session):
                return None

        if StatisticsParameter.WEEKLY.value in times:
            if not _insertStatistic(type, StatisticsParameter.WEEKLY, member, session):
                return None

        if StatisticsParameter.MONTHLY.value in times:
            if not _insertStatistic(type, StatisticsParameter.MONTHLY, member, session):
                return None

        if StatisticsParameter.YEARLY.value in times:
            if not _insertStatistic(type, StatisticsParameter.YEARLY, member, session):
                return None

        try:
            statistics = session.scalars(getQuery).all()
        except Exception as error:
            logger.error(f"couldn't fetch newly inserted current discord statistics for {member.display_name}",
                         exc_info=error, )
            return None

    return list(statistics)


def _insertStatistic(type: StatisticsParameter,
                     statistic_time: StatisticsParameter,
                     member: Member,
                     session: Session) -> bool:
    # noinspection PyTypeChecker
    insertQuery = (insert(CurrentDiscordStatistic)
                   .values(statistic_type=type.value,
                           statistic_time=statistic_time.value,
                           value=0,
                           discord_id=(select(DiscordUser.id)
                                       .where(DiscordUser.user_id == str(member.id))
                                       .scalar_subquery()),
                           ))

    try:
        session.execute(insertQuery)
        session.commit()

        logger.debug(f"inserted new current discord statistics for {member.display_name} "
                     f"and time: {statistic_time.value}")

        return True
    except Exception as error:
        logger.error(f"couldn't insert or commit current discord statistics for {member.display_name}",
                     exc_info=error, )

        return False
