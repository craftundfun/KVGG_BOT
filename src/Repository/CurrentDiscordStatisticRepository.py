import logging

from discord import Member

from src.DiscordParameters.StatisticsParameter import StatisticsParameter
from src.Services.Database import Database

logger = logging.getLogger("KVGG_BOT")


def getStatisticsForUser(database: Database, type: StatisticsParameter, member: Member) -> list[dict] | None:
    """
    Returns the statistics of all time-types from the database.
    If they don't exist yet, a new entry is created

    :param member: Member to retrieve all data from
    :param database:
    :return: List of the type and all times or None if a failure occurred
    """
    getQuery = ("SELECT * "
                "FROM current_discord_statistic "
                "WHERE statistic_type = %s AND discord_id = "
                "(SELECT id FROM discord WHERE user_id = %s)")
    # TODO dont create with 1 - but we have to because of a bug
    insertQuery = ("INSERT INTO current_discord_statistic (discord_id, statistic_time, statistic_type, value) "
                   "VALUES ((SELECT id FROM discord WHERE user_id = %s), %s, %s, %s)")

    if not (statistics := database.fetchAllResults(getQuery, (type.value, member.id,))):
        if not database.runQueryOnDatabase(insertQuery, (member.id, StatisticsParameter.WEEKLY.value, type.value, 1)):
            logger.error(f"couldn't insert weekly statistics for {member.display_name}")

            return None

        if not database.runQueryOnDatabase(insertQuery, (member.id, StatisticsParameter.MONTHLY.value, type.value, 1)):
            logger.error(f"couldn't insert monthly statistics for {member.display_name}")

            return None

        if not database.runQueryOnDatabase(insertQuery, (member.id, StatisticsParameter.YEARLY.value, type.value, 1)):
            logger.error(f"couldn't insert yearly statistics for {member.display_name}")

            return None

        if not (statistics := database.fetchAllResults(getQuery, (type.value, member.id,))):
            logger.error(f"couldn't fetch statistic of type {type.value} for {member.display_name} after inserting")

            return None
    elif len(statistics) != 3:
        logger.debug("less then 3 statistics, searching missing one and creating it")

        times = [StatisticsParameter.WEEKLY.value,
                 StatisticsParameter.MONTHLY.value,
                 StatisticsParameter.YEARLY.value, ]

        for stat in statistics:
            if stat['statistic_time'] in times:
                times.remove(stat['statistic_time'])

        for time in times:
            if not database.runQueryOnDatabase(insertQuery, (member.id, time, type.value)):
                logger.error(f"couldn't insert {time} statistics for {member.display_name}")

                return None

    logger.debug(f"fetched statistics for {member.display_name}")

    return statistics
