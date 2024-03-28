import logging

import Levenshtein
from discord import Member

from src.Services.Database_Old import Database_Old

logger = logging.getLogger("KVGG_BOT")


def getDiscordGame(database: Database_Old, activityName: str) -> dict | None:
    insertQuery = "INSERT INTO discord_game (name) VALUES (%s)"
    getQuery = "SELECT * FROM discord_game WHERE name = %s"
    game = database.fetchOneResult(getQuery, (activityName,))

    # found game with exact name
    if game:
        logger.debug("found activity with exact name")

        return game

    getQuery = "SELECT id, name FROM discord_game"
    gameId = -1

    # check for None here in case we have no games => Murphy's Law
    if (names := database.fetchAllResults(getQuery)) is None:
        logger.error("couldn't fetch names of games from database")

        return None

    for name in names:
        # if the name is similar enough
        if Levenshtein.distance(activityName.lower(), name['name'].lower(), score_cutoff=2) <= 2:
            gameId = name['id']

            logger.debug(f"found game without exact name: {activityName} and {name['name']}")
            break

    # no game with a matching name was found
    if gameId == -1:
        if not database.runQueryOnDatabase(insertQuery, (activityName,)):
            logger.error("couldn't insert new game with only the name in the database")

            return None

        logger.debug(f"inserted new game with name: {activityName}")

        getQuery = "SELECT * FROM discord_game WHERE name = %s"

        # fetch the new game to get the id
        if not (game := database.fetchOneResult(getQuery, (activityName,))):
            logger.error(f"couldn't fetch newly inserted game with name: {activityName}")

            return None
    else:
        getQuery = "SELECT * FROM discord_game WHERE id = %s"

        if not (game := database.fetchOneResult(getQuery, (gameId,))):
            logger.error(f"couldn't fetch existing game with ID: {gameId}")

            return None

    logger.debug(f"fetched game {activityName}")

    return game


def getGameDiscordRelation_Old(database: Database_Old,
                               member: Member,
                               activityName: str,
                               includeGameInformation: bool = False) -> dict | None:
    insertQuery = ("INSERT INTO game_discord_mapping (discord_id, discord_game_id) "
                   "VALUES ((SELECT id FROM discord WHERE user_id = %s), %s)")
    game: dict | None = getDiscordGame(database, activityName)

    if not game:
        logger.error("couldn't get game")

        return None

    getQuery = (f"SELECT gdm.*{', dg.application_id, dg.name' if includeGameInformation else ''} "
                "FROM game_discord_mapping gdm INNER JOIN discord_game dg ON gdm.discord_game_id = dg.id "
                "WHERE dg.id = %s "
                "AND gdm.discord_id = (SELECT id FROM discord WHERE user_id = %s)")

    if not (relation := database.fetchOneResult(getQuery, (game['id'], member.id,))):
        logger.debug(f"did not found relation for {member.display_name} and {activityName}")

        if not database.runQueryOnDatabase(insertQuery, (member.id, game['id'],)):
            logger.error(f"couldn't create new game_discord_relation for {member.display_name} and {activityName}")

            return None

        if not (relation := database.fetchOneResult(getQuery, (game['id'], member.id,))):
            logger.error("couldn't fetch newly created game_discord_relation")

            return None

    return relation
