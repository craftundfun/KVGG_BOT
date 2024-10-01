import logging

import Levenshtein
import discord
from discord import Member
from sqlalchemy import desc
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import MultipleResultsFound
from sqlalchemy.orm.exc import NoResultFound

from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Entities.Game.Entity.DiscordGame import DiscordGame
from src.Entities.Game.Entity.GameDiscordMapping import GameDiscordMapping

logger = logging.getLogger("KVGG_BOT")


def getDiscordGame(activity: discord.Activity, session: Session) -> DiscordGame | None:
    existingIdField = True

    try:
        # noinspection PyTypeChecker
        getQueryByID = select(DiscordGame).where(DiscordGame.external_game_id == activity.application_id, )
    # catch AttributeError if activity has no application_id
    except AttributeError:
        logger.debug(f"activity {activity.name} has no application_id")

        existingIdField = False

    # noinspection PyTypeChecker
    getQueryByName = select(DiscordGame).where(DiscordGame.name == activity.name, )

    try:
        if not existingIdField or not activity.application_id:
            # skip empty / non-existing application_id
            raise NoResultFound

        # noinspection PyUnboundLocalVariable
        game = session.scalars(getQueryByID).one()
    except MultipleResultsFound as error:
        logger.error(f"found multiple results for {activity.name}",
                     exc_info=error, )

        return None
    except NoResultFound:
        logger.debug(f"did not found game with external_id for {activity.name}")

        try:
            game = session.scalars(getQueryByName).one()
        except MultipleResultsFound as error:
            logger.error(f"found multiple results for game with name {activity.name}", exc_info=error, )

            return None
        except NoResultFound:
            logger.debug(f"did not found game with exact name {activity.name}")

            try:
                games = session.scalars(select(DiscordGame)).all()
            except Exception as error:
                logger.error("couldn't fetch all games", exc_info=error)

                return None
            else:
                logger.debug("traversing all games for Levenshtein distance")

                for game in games:
                    if Levenshtein.distance(activity.name.lower(), game.name.lower(), score_cutoff=2) <= 2:
                        logger.debug(f"found game without name {activity.name} by Levenshtein distance")

                        if existingIdField and activity.application_id and not game.external_game_id:
                            game.external_game_id = activity.application_id

                            session.commit()
                            logger.debug(f"added external_game_id {activity.application_id} to game without exact name "
                                         f"{activity.name}")

                        # found game without an exact name
                        return game

                # if we arrive here, we will have to insert a new game into the database
                try:
                    game = DiscordGame(name=activity.name,
                                       external_game_id=activity.application_id if existingIdField else None, )

                    session.add(game)
                    session.commit()
                except Exception as error:
                    logger.error(f"couldn't insert new game with name {activity.name}", exc_info=error)
                    session.rollback()

                    return None
                else:
                    return game
        else:
            logger.debug(f"fetched game with name {activity.name}")

            # dont overwrite existing external_game_id
            if existingIdField and activity.application_id and not game.external_game_id:
                game.external_game_id = activity.application_id

                session.commit()
                logger.debug(f"added external_game_id {activity.application_id} to game without exact name "
                             f"{activity.name}")

            # found game with exact name
            return game
    else:
        logger.debug(f"fetched game with external_id {activity.application_id}")

        # found game with external_id
        return game


def getGameDiscordRelation(session: Session,
                           member: Member,
                           activity: discord.Activity, ) -> GameDiscordMapping | None:
    if not (game := getDiscordGame(activity, session)):
        logger.error("couldn't get game")

        return None

    # noinspection PyTypeChecker
    insertQuery = insert(GameDiscordMapping).values(time_played_online=0,
                                                    time_played_offline=0,
                                                    discord_id=(select(DiscordUser.id)
                                                                .where(DiscordUser.user_id == str(member.id))
                                                                .scalar_subquery()),
                                                    discord_game_id=game.id, )
    # noinspection PyTypeChecker
    getQuery = (select(GameDiscordMapping)
                .where(GameDiscordMapping.discord_game_id == game.id,
                       GameDiscordMapping.discord_id == (select(DiscordUser.id)
                                                         .where(DiscordUser.user_id == str(member.id))
                                                         .scalar_subquery()), ))

    try:
        relation = session.scalars(getQuery).one()
    except MultipleResultsFound as error:
        logger.error(f"found multiple results for game relation for {member.display_name} and {activity.name}",
                     exc_info=error, )

        return None
    except NoResultFound:
        logger.debug(f"did not found relation for {member.display_name} and {activity.name}")

        try:
            session.execute(insertQuery)
            session.commit()
        except Exception as error:
            logger.error(f"couldn't insert new game relation for {member.display_name} and {activity.name}",
                         exc_info=error, )
            session.rollback()

            return None

        logger.debug(f"inserted new game relation for {member.display_name} and {activity.name}")

        try:
            relation = session.scalars(getQuery).one()
        except Exception as error:
            logger.error(f"couldn't fetch newly inserted game relation for {member.display_name} and {activity.name}",
                         exc_info=error, )

            return None
    except Exception as error:
        logger.debug(
            f"an error occurred while fetching DiscordGameRelation for {member.display_name} and {activity.name}",
            exc_info=error, )

        return None

    logger.debug(f"fetched game relation for {member.display_name} and {activity.name}")

    return relation


def getMostPlayedGames(session: Session, limit: int = 3) -> list[dict[str, str | int]] | None:
    """
    Fetches the most played games from the database based on time played online and offline.

    :return: [{"name": <str>, "time_played": <int>}]
    """
    getQuery = (select(DiscordGame.name, func.sum(GameDiscordMapping.time_played_online)
                       + func.sum(GameDiscordMapping.time_played_offline))
                .join(GameDiscordMapping)
                .group_by(GameDiscordMapping.discord_game_id)
                # this is shit, but I found no way to make this better -.-  -> FML
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
