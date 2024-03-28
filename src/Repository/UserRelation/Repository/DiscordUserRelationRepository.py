import logging
from datetime import datetime

from discord import Member
from sqlalchemy import select, or_, and_, insert
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound

from src.Repository.DiscordUser.Repository.DiscordUserRepository import getDiscordUser
from src.Repository.UserRelation.Entity.DiscordUserRelation import DiscordUserRelation

logger = logging.getLogger("KVGG_BOT")


def getRelationBetweenUsers(member_1: Member,
                            member_2: Member,
                            type: 'RelationTypeEnum',
                            session: Session) -> DiscordUserRelation | None:
    """
    Returns the relation of the given type and users

    :param member_2:
    :param member_1:
    :param type:
    :return:
    """
    if member_1.id == member_2.id:
        logger.debug("same member for relation")

        return None

    if member_1.bot or member_2.bot:
        logger.debug("one of the users were a bot")

        return None

    dcUserDb_1 = getDiscordUser(member_1, session)
    dcUserDb_2 = getDiscordUser(member_2, session)

    if not dcUserDb_1 or not dcUserDb_2:
        logger.warning(f"couldn't create relation, "
                       f"{member_1.display_name if not dcUserDb_1 else member_2.display_name} has no entity")

        return None

    getQuery = select(DiscordUserRelation).where(DiscordUserRelation.type == type.value,
                                                 or_(and_(DiscordUserRelation.discord_user_id_1 == dcUserDb_1.id,
                                                          DiscordUserRelation.discord_user_id_2 == dcUserDb_2.id),
                                                     and_(DiscordUserRelation.discord_user_id_1 == dcUserDb_2.id,
                                                          DiscordUserRelation.discord_user_id_2 == dcUserDb_1.id)))

    try:
        relation = session.scalars(getQuery).one()
    except NoResultFound:
        insertQuery = insert(DiscordUserRelation).values(discord_user_id_1=dcUserDb_1.id,
                                                         discord_user_id_2=dcUserDb_2.id,
                                                         type=type.value,
                                                         created_at=datetime.now(), )

        try:
            session.execute(insertQuery)
            session.commit()
        except Exception as error:
            logger.error(f"couldn't insert new Relation for {member_1.display_name} and {member_2.display_name}",
                         exc_info=error, )
            session.rollback()

            return None

        logger.debug(f"created new Relation for {member_1.display_name} and {member_2.display_name}")

        try:
            relation = session.scalars(getQuery).one()
        except Exception as error:
            logger.error(f"couldn't fetch newly inserted Relation for {member_1.display_name} and "
                         f"{member_2.display_name}",
                         exc_info=error, )

            return None
    except Exception as error:
        logger.error(f"couldn't fetch relation for {member_1.display_name}, {member_2.display_name} and {type.value}",
                     exc_info=error, )

        return None

    return relation
