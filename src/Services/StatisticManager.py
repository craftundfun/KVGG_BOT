import logging
from datetime import datetime

from discord import Member, Client

from src.DiscordParameters.StatisticsParameter import StatisticsParameter
from src.Helper.GetFormattedTime import getFormattedTime
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Id.GuildId import GuildId
from src.Repository.CurrentDiscordStatisticRepository import getStatisticsForUser
from src.Services.Database import Database
from src.Services.NotificationService import NotificationService

logger = logging.getLogger("KVGG_BOT")


class StatisticManager:

    def __init__(self, client: Client):
        self.client = client

        self.notificationService = NotificationService(self.client)

    def runStatistics(self, userStatistics: list[dict] | None):
        """
        Creates the specified statistic type for every user in the database

        :param userStatistics: List of DiscordUsers
        """
        if not userStatistics:
            return

        database = Database()
        insertQuery = ("INSERT INTO statistic_log (time_online, type, discord_user_id, created_at) "
                       "VALUES (%s, %s, %s, %s)")
        deleteQuery = "DELETE FROM current_discord_statistic WHERE id = %s"
        now = datetime.now()

        for data in userStatistics:
            logger.debug(f"running statistic for DiscordID: {data['discord_id']}")

            # only create statistic log if the type is online
            if data['statistic_type'] == StatisticsParameter.ONLINE.value and data['value'] > 0:
                if not database.runQueryOnDatabase(insertQuery,
                                                   (data['value'], data['statistic_time'], data['discord_id'], now)):
                    logger.error(f"couldn't insert statistics for DiscordID: {data['discord_id']}")

            if not database.runQueryOnDatabase(deleteQuery, (data['id'],)):
                logger.error(f"couldn't delete statistics for DiscordID: {data['discord_id']}")

    def increaseStatistic(self, type: StatisticsParameter, member: Member, value: int = 1):
        logger.debug(f"increasing statistics for {member.display_name} and type {type.value}")

        database = Database()
        statistics: list[dict] = getStatisticsForUser(database, type, member)

        if not statistics:
            logger.error(f"got no statistics for {member.display_name}, aborting to increase")

            return

        # increase weekly, monthly and yearly
        for statistic in statistics:
            statistic['value'] += value

            saveQuery, nones = writeSaveQuery("current_discord_statistic", statistic['id'], statistic)

            if not database.runQueryOnDatabase(saveQuery, nones):
                logger.error(f"couldn't increase statistics for {member.display_name} and time "
                             f"{statistic['statistic_time']}")

    async def runRetrospectForUsers(self, time: StatisticsParameter):
        """
        Creates a retrospect for all users who have statistics for the given time period.

        :param time: Time period to send the retrospect for
        """
        database = Database()
        query = "SELECT id, user_id FROM discord"

        if not (users := database.fetchAllResults(query)):
            logger.error("couldn't fetch all users from database to create retrospects")

            return

        for user in users:
            logger.debug(f"creating retrospect for user_id: {user['user_id']}")

            member = self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(int(user['user_id']))

            if not member:
                logger.warning("couldn't fetch member from guild")

                continue

            def getStatisticForTime(statistics: list[dict]) -> dict | None:
                if not statistics:
                    return None

                for stat in statistics:
                    if stat['statistic_time'] == time.value:
                        return stat

                return None

            onlineStatistic = getStatisticForTime(getStatisticsForUser(database, StatisticsParameter.ONLINE, member))
            streamStatistic = getStatisticForTime(getStatisticsForUser(database, StatisticsParameter.STREAM, member))
            messageStatistic = getStatisticForTime(getStatisticsForUser(database, StatisticsParameter.MESSAGE, member))
            commandStatistic = getStatisticForTime(getStatisticsForUser(database, StatisticsParameter.COMMAND, member))

            if not onlineStatistic and not streamStatistic and not messageStatistic and not commandStatistic:
                logger.debug(f"{member.display_name} has no statistics this {time.value}")

                continue
            elif (onlineStatistic['value'] == 0 and streamStatistic['value'] == 0
                  and messageStatistic['value'] == 0 and commandStatistic['value'] == 0):
                logger.debug(f"{member.display_name} has no real values")

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

            if onlineStatistic and onlineStatistic['value'] > 0:
                message += f"-\tDu warst {getFormattedTime(onlineStatistic['value'])} Stunden online.\n"

            if streamStatistic and streamStatistic['value'] > 0:
                message += (f"-\tDu warst hast insgesamt {getFormattedTime(streamStatistic['value'])} Stunden "
                            f"gestreamt.\n")

            if messageStatistic and messageStatistic['value'] > 0:
                message += f"-\tDu hast ganze {messageStatistic['value']} Nachrichten verfasst.\n"

            if commandStatistic and commandStatistic['value'] > 0:
                message += f"-\tDu hast mich {commandStatistic['value']} Mal genutzt.\n"

            await self.notificationService.sendRetrospect(member, message.rstrip("\n"))
