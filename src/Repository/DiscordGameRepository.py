import logging

from discord import Member
from discord.activity import Activity

from src.Services.Database import Database

logger = logging.getLogger("KVGG_BOT")


def getDiscordGame(database: Database, activity: Activity) -> dict | None:
    getQuery = "SELECT * FROM discord_game WHERE application_id = %s"
    insertQuery = "INSERT INTO discord_game (application_id, name) VALUES (%s, %s)"

    if not (game := database.fetchOneResult(getQuery, (activity.application_id,))):
        logger.debug(f"game with id {activity.application_id} does not exist in the database yet")

        if not database.runQueryOnDatabase(insertQuery, (activity.application_id, activity.name,)):
            logger.error(f"couldn't add new game {activity.name} with id {activity.application_id} to database")

            return None

        if not (game := database.fetchOneResult(getQuery, (activity.application_id,))):
            logger.error(f"couldn't fetch newly added game {activity.name} with id {activity.application_id}")

            return None

    logger.debug(f"fetched game {activity.name}")

    return game


def getGameDiscordRelation(database: Database, member: Member, activity: Activity) -> dict | None:
    getQuery = ("SELECT gdm.* "
                "FROM game_discord_mapping gdm INNER JOIN discord_game dg ON gdm.discord_game_id = dg.id "
                "WHERE dg.application_id = %s "
                "AND gdm.discord_id = (SELECT id FROM discord WHERE user_id = %s)")
    insertQuery = ("INSERT INTO game_discord_mapping (discord_id, discord_game_id) "
                   "VALUES ((SELECT id FROM discord WHERE user_id = %s), %s)")

    if not (relation := database.fetchOneResult(getQuery, (activity.application_id, member.id,))):
        logger.debug(f"did not found relation for {member.display_name} and {activity.name}")

        if not (game := getDiscordGame(database, activity)):
            logger.error("couldn't fetch game => cant fetch game_discord_relation")

            return None

        if not database.runQueryOnDatabase(insertQuery, (member.id, game['id'],)):
            logger.error(f"couldn't create new game_discord_relation for {member.display_name} and {activity.name}")

            return None

        if not (relation := database.fetchOneResult(getQuery, (activity.application_id, member.id,))):
            logger.error("couldn't fetch newly created game_discord_relation")

            return None

    return relation
