import json
import logging
import math

from discord import Member
from sqlalchemy import select, insert, literal_column
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.DiscordParameters.ExperienceParameter import ExperienceParameter
from src.Repository.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Repository.DiscordUser.Repository.DiscordUserRepository import getDiscordUser
from src.Repository.Experience.Entity.Experience import Experience

logger = logging.getLogger("KVGG_BOT")


def getExperience(member: Member, session: Session) -> Experience | None:
    """
        Returns the Experience from the given user. If no entry exists, it will create one

        :param member: User of the Experience
        :param session: Session of the database connection
        :return:
        """
    logger.debug("fetching experience")

    getQuery = (select(Experience)
                .where(Experience.discord_user_id == (select(DiscordUser.id)
                                                      .where(DiscordUser.user_id == str(member.id))
                                                      .scalar_subquery()))
                )

    try:
        xp = session.scalars(getQuery).one()
    except NoResultFound:
        logger.debug(f"creating experience for {member.display_name}")

        dcUserDb = getDiscordUser(member, session)

        if not dcUserDb:
            logger.error(f"cant create experience because of missing DiscordUser for {member.display_name}")

            return None

        xpAmount = _calculateXpFromPreviousData(dcUserDb)
        xpBoosts = _calculateXpBoostsFromPreviousData(dcUserDb)

        insertQuery = insert(Experience).values(xp_amount=xpAmount,
                                                xp_boosts_inventory=xpBoosts if xpBoosts else literal_column("NULL"),
                                                discord_user_id=dcUserDb.id, )

        try:
            session.execute(insertQuery)
            session.commit()
        except Exception as error:
            logger.error(f"could not insert (or commit) experience for {member.display_name}", exc_info=error)
            session.rollback()

            return None

        try:
            xp = session.scalars(getQuery).one()
        except Exception as error:
            logger.error("couldn't fetch newly inserted experience for {member.display_name}", exc_info=error)
            session.rollback()

            return None
    except Exception as error:
        logger.error(f"couldn't fetch experience for {member.display_name}", exc_info=error)

        return None

    return xp


def _calculateXpBoostsFromPreviousData(dcUserDb: DiscordUser) -> str | None:
    """
    Calculates the XP-Boosts earned until now

    :param dcUserDb: DiscordUser to calculate the XP-Boosts for
    :return: None | string JSON of earned boots, otherwise None
    """
    logger.debug(f"calculating xp boosts from previous data for {dcUserDb.username}")

    timeOnline = dcUserDb.time_online
    timeStreamed = dcUserDb.time_streamed

    # get a floored number of grant-able boosts
    numberAchievementBoosts = timeOnline / (AchievementParameter.ONLINE_TIME_HOURS.value * 60)
    flooredNumberAchievementBoosts = math.floor(numberAchievementBoosts)
    intNumberAchievementBoosts = int(flooredNumberAchievementBoosts)

    if intNumberAchievementBoosts == 0:
        logger.debug(f"no boosts to grant for {dcUserDb.username}")

        # no time = no streams, so we don't have to check for that as well
        return None

    if intNumberAchievementBoosts > ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value:
        intNumberAchievementBoosts = ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value

    boosts = []

    for i in range(intNumberAchievementBoosts):
        boost = {
            'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_ONLINE.value,
            'remaining': ExperienceParameter.XP_BOOST_ONLINE_DURATION.value,
            'description': ExperienceParameter.DESCRIPTION_ONLINE.value,
        }

        boosts.append(boost)

    # if the user never streamed or inventory is already full return it
    if not timeStreamed or len(boosts) >= ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value:
        logger.debug(f"{intNumberAchievementBoosts} online boosts granted")

        return json.dumps(boosts)

    numberAchievementBoosts = timeStreamed / (AchievementParameter.STREAM_TIME_HOURS.value * 60)
    flooredNumberAchievementBoosts = math.floor(numberAchievementBoosts)
    intNumberAchievementBoosts = int(flooredNumberAchievementBoosts)

    if intNumberAchievementBoosts == 0:
        logger.debug(f"no boosts to grant for {dcUserDb.username}")

        return json.dumps(boosts)

    if len(boosts) + intNumberAchievementBoosts >= ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value:
        intNumberAchievementBoosts = ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value - len(boosts)

    for i in range(intNumberAchievementBoosts):
        boost = {
            'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_STREAM.value,
            'remaining': ExperienceParameter.XP_BOOST_STREAM_DURATION.value,
            'description': ExperienceParameter.DESCRIPTION_STREAM.value,
        }

        boosts.append(boost)

    logger.debug(f"{intNumberAchievementBoosts} online and stream boosts granted")

    return json.dumps(boosts)


def _calculateXpFromPreviousData(dcUserDb: DiscordUser) -> int:
    """
    Calculates the XP earned until now

    :param dcUserDb: Member to calculate the XP
    :return: int
    """
    logger.debug(f"calculating xp from previous data for {dcUserDb.username}")

    amount = 0
    amount += dcUserDb.time_online * ExperienceParameter.XP_FOR_ONLINE.value
    amount += dcUserDb.time_streamed * ExperienceParameter.XP_FOR_STREAMING.value
    amount += dcUserDb.message_count_all_time * ExperienceParameter.XP_FOR_MESSAGE.value
    amount += dcUserDb.command_count_all_time * ExperienceParameter.XP_FOR_COMMAND.value

    logger.debug(f"calculated {amount} xp for {dcUserDb.username}")

    return amount
