import logging

import Levenshtein
from discord import Member
from discord.activity import Activity

from src.Services.Database import Database

logger = logging.getLogger("KVGG_BOT")


def getDiscordGame(database: Database, activity: Activity = None, gameName: str = None) -> dict | None:
    if not activity and not gameName:
        logger.error("no activity or name given")

        return None

    insertQuery = "INSERT INTO discord_game (application_id, name) VALUES (%s, %s)"

    if activity:
        getQuery = "SELECT * FROM discord_game WHERE application_id = %s"

        if not (game := database.fetchOneResult(getQuery, (activity.application_id,))):
            logger.debug(f"game with id {activity.application_id} does not exist in the database yet")

            if not database.runQueryOnDatabase(insertQuery, (activity.application_id, activity.name,)):
                logger.error(f"couldn't add new game {activity.name} with id {activity.application_id} to database")

                return None

            if not (game := database.fetchOneResult(getQuery, (activity.application_id,))):
                logger.error(f"couldn't fetch newly added game {activity.name} with id {activity.application_id}")

                return None
    else:
        getQuery = "SELECT id, name FROM discord_game"
        gameId = -1

        # check for None here in case we have no games => Murphy's Law
        if (names := database.fetchAllResults(getQuery)) is None:
            logger.error("couldn't fetch names of games from database")

            return None

        for name in names:
            if Levenshtein.distance(gameName, name['name'], score_cutoff=2) <= 2:
                gameId = name['id']

                break

        # no game with a matching name was found
        if gameId == -1:
            if not database.runQueryOnDatabase(insertQuery, (None, gameName,)):
                logger.error("couldn't insert new game with only the name in the database")

                return None

            getQuery = "SELECT * FROM discord_game WHERE name = %s"

            # fetch the new game to get the id
            if not (game := database.fetchOneResult(getQuery, (gameName,))):
                logger.error(f"couldn't fetch newly inserted game with name: {gameName}")

                return None
        else:
            getQuery = "SELECT * FROM discord_game WHERE id = %s"

            if not (game := database.fetchOneResult(getQuery, (gameId,))):
                logger.error(f"couldn't fetch existing game with ID: {gameId}")

                return None

    logger.debug(f"fetched game {activity.name if activity else gameName}")

    return game


def getGameDiscordRelation(database: Database,
                           member: Member,
                           activity: Activity = None,
                           gameName: str = None) -> dict | None:
    insertQuery = ("INSERT INTO game_discord_mapping (discord_id, discord_game_id) "
                   "VALUES ((SELECT id FROM discord WHERE user_id = %s), %s)")

    if activity:
        getQuery = ("SELECT gdm.* "
                    "FROM game_discord_mapping gdm INNER JOIN discord_game dg ON gdm.discord_game_id = dg.id "
                    "WHERE dg.application_id = %s "
                    "AND gdm.discord_id = (SELECT id FROM discord WHERE user_id = %s)")

        if not (relation := database.fetchOneResult(getQuery, (activity.application_id, member.id,))):
            logger.debug(f"did not found relation for {member.display_name} and {activity.name}")

            if not (game := getDiscordGame(database, activity, gameName)):
                logger.error("couldn't fetch game => cant fetch game_discord_relation")

                return None

            if not database.runQueryOnDatabase(insertQuery, (member.id, game['id'],)):
                logger.error(f"couldn't create new game_discord_relation for {member.display_name} and {activity.name}")

                return None

            if not (relation := database.fetchOneResult(getQuery, (activity.application_id, member.id,))):
                logger.error("couldn't fetch newly created game_discord_relation")

                return None
    elif gameName:
        game: dict | None = getDiscordGame(database, None, gameName)

        if not game:
            logger.error("couldn't get game")

            return None

        getQuery = ("SELECT gdm.* "
                    "FROM game_discord_mapping gdm INNER JOIN discord_game dg ON gdm.discord_game_id = dg.id "
                    "WHERE dg.id = %s "
                    "AND gdm.discord_id = (SELECT id FROM discord WHERE user_id = %s)")

        if not (relation := database.fetchOneResult(getQuery, (game['id'], member.id,))):
            logger.debug(f"did not found relation for {member.display_name} and {gameName}")

            if not database.runQueryOnDatabase(insertQuery, (member.id, game['id'],)):
                logger.error(f"couldn't create new game_discord_relation for {member.display_name} and {gameName}")

                return None

            if not (relation := database.fetchOneResult(getQuery, (game['id'], member.id,))):
                logger.error("couldn't fetch newly created game_discord_relation")

                return None
    else:
        logger.error("no name or activity provided")

        return None

    return relation
