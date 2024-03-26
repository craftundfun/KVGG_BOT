import logging

import Levenshtein
from discord import Member
from sqlalchemy import desc
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import MultipleResultsFound
from sqlalchemy.orm.exc import NoResultFound

from src.Repository.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Repository.Game.Entity.Game import Game
from src.Repository.Game.Entity.GameDiscordMapping import GameDiscordMapping

logger = logging.getLogger("KVGG_BOT")


def getDiscordGame(activityName: str, session: Session) -> Game | None:
    insertQuery = insert(Game).values(name=activityName)
    getQuery = select(Game).where(Game.name == activityName)

    try:
        game = session.scalars(getQuery).one()
    except MultipleResultsFound as error:
        logger.error(f"multiple results found for game: {activityName}", exc_info=error)

        return None
    except NoResultFound:
        logger.debug(f"did not found exact name match for {activityName}")

        getGamesQuery = select(Game)

        try:
            games = session.scalars(getGamesQuery).all()
        except NoResultFound as error:
            logger.error("did not found any game in database", exc_info=error)

            return None

        for game in games:
            if Levenshtein.distance(activityName.lower(), game.name.lower(), score_cutoff=2) <= 2:
                logger.debug(f"found game without exact name: {activityName} and {game.name}")

                return game

        # if we arrive here, we will have to insert a new game into the database
        try:
            session.execute(insertQuery)
            session.commit()
        except Exception as error:
            logger.error(f"couldn't insert new game with name: {activityName}", exc_info=error)
            session.rollback()

            return None

        try:
            game = session.scalars(getQuery).one()
        except Exception as error:
            logger.error(f"couldn't fetch newly inserted game with name: {activityName}", exc_info=error)

            return None

        logger.debug(f"successfully fetched new inserted game with name: {activityName}")
    except Exception as error:
        logger.error(f"an error occurred while fetching discord game: {activityName}", exc_info=error)

        return None
    else:
        logger.debug("found activity with exact name")

    return game


def getGameDiscordRelation(session: Session,
                           member: Member,
                           activityName: str,
                           ) -> GameDiscordMapping | None:
    if not (game := getDiscordGame(activityName, session)):
        logger.error("couldn't get game")

        return None

    insertQuery = insert(GameDiscordMapping).values(time_played_online=0,
                                                    time_played_offline=0,
                                                    discord_id=(select(DiscordUser.id)
                                                                .where(DiscordUser.user_id == str(member.id))
                                                                .scalar_subquery()),
                                                    discord_game_id=game.id, )
    getQuery = (select(GameDiscordMapping)
                .where(GameDiscordMapping.discord_game_id == game.id,
                       GameDiscordMapping.discord_id == (select(DiscordUser.id)
                                                         .where(DiscordUser.user_id == str(member.id))
                                                         .scalar_subquery())
                       )
                )

    try:
        relation = session.scalars(getQuery).one()
    except MultipleResultsFound as error:
        logger.error(f"found multiple results for game relation for {member.display_name} and {activityName}",
                     exc_info=error, )

        return None
    except NoResultFound:
        logger.debug(f"did not found relation for {member.display_name} and {activityName}")

        try:
            session.execute(insertQuery)
            session.commit()
        except Exception as error:
            logger.error(f"couldn't insert new game relation for {member.display_name} and {activityName}",
                         exc_info=error, )
            session.rollback()

            return None

        logger.debug(f"inserted new game relation for {member.display_name} and {activityName}")

        try:
            relation = session.scalars(getQuery).one()
        except Exception as error:
            logger.error(f"couldn't fetch newly inserted game relation for {member.display_name} and {activityName}",
                         exc_info=error, )

            return None
    except Exception as error:
        logger.debug(
            f"an error occurred while fetching DiscordGameRelation for {member.display_name} and {activityName}",
            exc_info=error, )

        return None

    logger.debug(f"fetched game relation for {member.display_name} and {activityName}")

    return relation


def getMostPlayedGames(session: Session, limit: int = 3) -> list[dict[str, str | int]] | None:
    """
    Fetches the most played games from the database based on time played online and offline.

    :return: [{"name": <str>, "time_played": <int>}]
    """
    getQuery = (select(Game.name, func.sum(GameDiscordMapping.time_played_online)
                       + func.sum(GameDiscordMapping.time_played_offline))
                .join(GameDiscordMapping)
                .group_by(GameDiscordMapping.discord_game_id)
                # this is shit, but I found no way to make this better -.-
                .order_by(desc(func.sum(GameDiscordMapping.time_played_online)
                               + func.sum(GameDiscordMapping.time_played_offline)))
                .limit(limit))

    try:
        games = session.execute(getQuery).all()
    except Exception as error:
        logger.error("couldn't fetch most played games from database", exc_info=error)

        return None

    logger.debug("fetched most played games")

    return [{"name": game[0], "time_played": int(game[1])} for game in games]
