import logging
from datetime import datetime

from discord import Member, Client
from sqlalchemy.orm import Session

from src.DiscordParameters.StatisticsParameter import StatisticsParameter
from src.Helper.GetFormattedTime import getFormattedTime
from src.Id.GuildId import GuildId
from src.Manager.NotificationManager import NotificationService
from src.Repository.CurrentDiscordStatisticRepository import getStatisticsForUser_OLD
from src.Repository.Statistic.Entity.CurrentDiscordStatistic import CurrentDiscordStatistic
from src.Repository.Statistic.Repository.StatisticRepository import getStatisticsForUser
from src.Services.Database_Old import Database_Old

logger = logging.getLogger("KVGG_BOT")


class StatisticManager:

    def __init__(self, client: Client):
        self.client = client

        self.notificationService = NotificationService(self.client)

    # TODO save also activity and stream times (add statistic_type column first)
    def saveStatisticsToStatisticLog(self, time: StatisticsParameter):
        """
        Saves the statistics (currently only online statistic) to the statistic-log database.

        :param time: Time to add statistics to
        """
        query = ("SELECT * "
                 "FROM current_discord_statistic "
                 "WHERE statistic_time = %s")
        insertQuery = ("INSERT INTO statistic_log (time_online, type, discord_user_id, created_at) "
                       "VALUES (%s, %s, %s, %s)")
        deleteQuery = "DELETE FROM current_discord_statistic WHERE id = %s"
        now = datetime.now()
        listOfInsertedUsers = []
        database = Database_Old()

        if not (userStatistics := database.fetchAllResults(query, (time,))):
            logger.error(f"couldn't fetch all statistics for {time}")

            return

        for data in userStatistics:
            logger.debug(f"running statistic for DiscordID: {data['discord_id']}")

            # only create statistic log if the type is online
            if data['statistic_type'] == StatisticsParameter.ONLINE.value and data['value'] > 0:
                if not database.runQueryOnDatabase(insertQuery, (data['value'], time, data['discord_id'], now)):
                    logger.error(f"couldn't insert statistics for DiscordID: {data['discord_id']}")

                listOfInsertedUsers.append(data['discord_id'])

            # delete statistic regardless of the type
            if not database.runQueryOnDatabase(deleteQuery, (data['id'],)):
                logger.error(f"couldn't delete statistics for DiscordID: {data['discord_id']}")

        query = "SELECT id FROM discord"

        if not (users := database.fetchAllResults(query)):
            logger.error(f"couldn't fetch all DiscordUsers")

            return

        # add "empty" statistics for users without any
        for user in users:
            if user['id'] in listOfInsertedUsers:
                continue

            logger.debug(f"DiscordID: {user['id']} had no previous online statistics, inserting 0")

            if not database.runQueryOnDatabase(insertQuery, (0, time, user['id'], now)):
                logger.error(f"couldn't insert statistics for DiscordID: {user['id']}")

                continue

    def increaseStatistic(self, type: StatisticsParameter, member: Member, session: Session, value: int = 1):
        """
        Increases the value of the given statistic in each time period.

        :param type: The type of the statistic
        :param member: The member whose statistic is increases
        :param value: The value to add, standard value of 1.
        :param session: The session to use for the database
        """
        logger.debug(f"increasing statistics for {member.display_name} and type {type.value}")

        statistics: list[CurrentDiscordStatistic] = getStatisticsForUser(type, member, session)

        if not statistics:
            logger.error(f"got no statistics for {member.display_name}, aborting to increase")

            return

        # increase weekly, monthly and yearly
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

    async def runRetrospectForUsers(self, time: StatisticsParameter):
        """
        Creates a retrospect for all users who have statistics for the given time period.

        :param time: Time period to send the retrospect for
        """
        database = Database_Old()
        query = ("SELECT DISTINCT d.id, d.user_id "
                 "FROM discord d INNER JOIN current_discord_statistic cds ON cds.discord_id = d.id")

        if not (users := database.fetchAllResults(query)):
            logger.error("couldn't fetch all users from database to create retrospects")

            return

        if not (guild := self.client.get_guild(GuildId.GUILD_KVGG.value)):
            logger.error("couldn't fetch guild")

            return

        for user in users:
            logger.debug(f"creating retrospect for user_id: {user['user_id']}")

            member = guild.get_member(int(user['user_id']))

            if not member:
                logger.warning("couldn't fetch member from guild")

                continue

            def getStatisticForTime(statistics: list[dict]) -> dict | None:
                """
                Filters all the given statistics for the wanted time.

                [statistic.YEAR, statistic.MONTH, statistic.WEEK] =wanted is week> [statistic.WEEK]
                """
                if not statistics:
                    return None

                for stat in statistics:
                    if stat['statistic_time'] == time.value:
                        return stat

                return None

            statistics = dict()
            statistics[StatisticsParameter.ONLINE.value] = (
                getStatisticForTime(getStatisticsForUser_OLD(database, StatisticsParameter.ONLINE, member))
            )
            statistics[StatisticsParameter.STREAM.value] = (
                getStatisticForTime(getStatisticsForUser_OLD(database, StatisticsParameter.STREAM, member))
            )
            statistics[StatisticsParameter.MESSAGE.value] = (
                getStatisticForTime(getStatisticsForUser_OLD(database, StatisticsParameter.MESSAGE, member))
            )
            statistics[StatisticsParameter.COMMAND.value] = (
                getStatisticForTime(getStatisticsForUser_OLD(database, StatisticsParameter.COMMAND, member))
            )
            statistics[StatisticsParameter.ACTIVITY.value] = (
                getStatisticForTime(getStatisticsForUser_OLD(database, StatisticsParameter.ACTIVITY, member))
            )

            allNone = True
            allZero = True

            for key in statistics.keys():
                if statistics[key]:
                    allNone = False

                    if statistics[key]['value'] != 0:
                        allZero = False

            if allNone or allZero:
                logger.debug(f"{member.display_name} has no statistics this {time.value}: "
                             f"allNone = {allNone}, allZero = {allZero}")

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

            message = f"__**Hey {member.display_name}, hier ist dein Rückblick für {getCorrectTimePeriod()}!**__\n\n"

            if (online := statistics[StatisticsParameter.ONLINE.value]) and online['value'] > 0:
                message += f"-\tDu warst {getFormattedTime(online['value'])} Stunden online.\n"

            if (stream := statistics[StatisticsParameter.STREAM.value]) and stream['value'] > 0:
                message += (f"-\tDu hast insgesamt {getFormattedTime(stream['value'])} Stunden "
                            f"gestreamt.\n")

            if (activity := statistics[StatisticsParameter.ACTIVITY.value]) and activity['value'] > 0:
                message += (f"-\tDu hast {getFormattedTime(activity['value'])} Stunden gespielt oder "
                            f"Programme genutzt.\n")

            if (messageStatistic := statistics[StatisticsParameter.MESSAGE.value]) and messageStatistic['value'] > 0:
                message += f"-\tDu hast ganze {messageStatistic['value']} Nachrichten verfasst.\n"

            if (command := statistics[StatisticsParameter.COMMAND.value]) and command['value'] > 0:
                message += f"-\tDu hast mich {command['value']} Mal genutzt (aka. Commands genutzt).\n"

            await self.notificationService.sendRetrospect(member, message.rstrip("\n"))

            logger.debug(f"sent retrospect to {member.display_name}")
