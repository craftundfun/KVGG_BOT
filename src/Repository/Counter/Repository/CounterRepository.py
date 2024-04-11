import logging

from discord import Member
from sqlalchemy import select, insert
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound

from src.Repository.Counter.Entity.Counter import Counter
from src.Repository.Counter.Entity.CounterDiscordMapping import CounterDiscordMapping
from src.Repository.DiscordUser.Entity.DiscordUser import DiscordUser

logger = logging.getLogger("KVGG_BOT")


def getCounterDiscordMapping(member: Member, counterName: str, session: Session) -> CounterDiscordMapping | None:
    """
    Fetches and creates new CounterDiscordMappings. THE COUNTER HAS TO EXIST.

    :return: CounterDiscordMapping or None
    """
    checkpoint = session.begin_nested()
    # noinspection PyTypeChecker
    getQuery = (select(CounterDiscordMapping)
                .where(CounterDiscordMapping.discord_id == (select(DiscordUser.id)
                                                            .where(DiscordUser.user_id == str(member.id))
                                                            .scalar_subquery()),
                       CounterDiscordMapping.counter_id == (select(Counter.id)
                                                            .where(Counter.name == counterName.lower())
                                                            .scalar_subquery())))

    try:
        counterDiscordMapping = session.scalars(getQuery).one()
    except NoResultFound:
        # noinspection PyTypeChecker
        insertQuery = insert(CounterDiscordMapping).values(counter_id=(select(Counter.id)
                                                                       .where(Counter.name == counterName.lower())
                                                                       .scalar_subquery()),
                                                           discord_id=(select(DiscordUser.id)
                                                                       .where(DiscordUser.user_id == str(member.id))
                                                                       .scalar_subquery()), )

        try:
            session.execute(insertQuery)
            session.commit()
        except Exception as error:
            logger.error(f"couldn't insert new CounterDiscordMapping for {member.display_name} and {counterName}",
                         exc_info=error, )
            checkpoint.rollback()
            checkpoint.close()

            return None

        try:
            counterDiscordMapping = session.scalars(getQuery).one()
        except Exception as error:
            logger.error(f"couldn't fetch newly inserted CounterDiscordMapping for {member.display_name} "
                         f"and {counterName}", exc_info=error)
            checkpoint.close()

            return None
    except Exception as error:
        logger.error(f"couldn't fetch CounterDiscordMapping for {member.display_name} and {counterName}",
                     exc_info=error, )
        checkpoint.rollback()

        return None
    finally:
        checkpoint.close()

    return counterDiscordMapping
