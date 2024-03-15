import logging

from discord import Member

from src.Services.Database_Old import Database_Old

logger = logging.getLogger("KVGG_BOT")


def getNotificationSettings(member: Member, database: Database_Old) -> dict | None:
    """
    Fetches the notification settings of the given Member from our database.

    :param member: Member, whose settings will be fetched
    :param database: Database
    :return: None if no settings were found, dict otherwise
    """
    query = ("SELECT * "
             "FROM notification_setting "
             "WHERE discord_id = "
             "(SELECT id FROM discord WHERE user_id = %s)")

    if not (settings := database.fetchOneResult(query, (member.id,))):
        logger.debug("couldn't fetch notification settings from database, creating new ones")

        insertQuery = ("INSERT INTO notification_setting (discord_id) "
                       "VALUES ((SELECT id FROM discord WHERE user_id = %s))")

        if not database.runQueryOnDatabase(insertQuery, (member.id,)):
            logger.error(f"couldn't create notification settings for {member.name}")

            return None

        if not (settings := database.fetchOneResult(query, (member.id,))):
            logger.error(f"couldn't fetch notification settings for {member.display_name}")

            return None

    return settings
