import logging

from discord import Member
from sqlalchemy import select, insert
from sqlalchemy.orm import Session

from src.DiscordParameters.StatisticsParameter import StatisticsParameter
from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Entities.DiscordUser.Repository.DiscordUserRepository import getDiscordUser
from src.Entities.Statistic.Entity.CurrentDiscordStatistic import CurrentDiscordStatistic

logger = logging.getLogger("KVGG_BOT")


def getCurrentStatisticsForUser(type: StatisticsParameter,
                                member: Member,
                                session: Session, ) -> list[CurrentDiscordStatistic] | None:
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

    # we can assume here the specified user has no statistics at all
    if not statistics:
        logger.debug(f"no current statistics found for {member.display_name}, creating new ones")

        if not (dcUserDb := getDiscordUser(member, session)):
            logger.error(f"couldn't fetch DiscordUser for {member.display_name}")

            return None

        for time in StatisticsParameter.getTimeValues():
            for type in StatisticsParameter.getTypeValues():
                insertQuery = insert(CurrentDiscordStatistic).values(statistic_type=type,
                                                                     statistic_time=time,
                                                                     value=0,
                                                                     discord_id=dcUserDb.id, )

                try:
                    session.execute(insertQuery)
                except Exception as error:
                    logger.error(f"couldn't insert statistics for {dcUserDb}, type: {type} and time: {time}",
                                 exc_info=error, )

        try:
            session.commit()
        except Exception as error:
            logger.error(f"couldn't commit new statistics for {dcUserDb}", exc_info=error)

            return None

        try:
            statistics = session.scalars(getQuery).all()
        except Exception as error:
            logger.error(f"an error occurred while fetching newly inserted statistics for {member.display_name}",
                         exc_info=error, )

            return None

        if not statistics:
            logger.error(f"couldn't fetch newly inserted statistics for {member.display_name}")

            return None

    return list(statistics)
