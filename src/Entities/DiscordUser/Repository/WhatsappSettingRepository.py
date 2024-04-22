import logging

from discord import Member
from sqlalchemy import select, insert
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound

from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Entities.DiscordUser.Entity.WhatsappSetting import WhatsappSetting
from src.Entities.User.Entity.User import User

logger = logging.getLogger("KVGG_BOT")


def getWhatsappSetting(member: Member, session: Session) -> WhatsappSetting | None:
    # noinspection PyTypeChecker
    getQuery = (select(WhatsappSetting)
                .where(WhatsappSetting.discord_user_id == (select(DiscordUser.id)
                                                           .where(DiscordUser.user_id == str(member.id))
                                                           .scalar_subquery())))

    try:
        whatsappSetting = session.scalars(getQuery).one()
    except NoResultFound:
        # noinspection PyTypeChecker
        getUserQuery = select(User).where(User.api_key_whats_app.is_not(None),
                                          User.phone_number.is_not(None),
                                          User.discord_user_id == (select(DiscordUser.id)
                                                                   .where(DiscordUser.user_id == str(member.id))
                                                                   .scalar_subquery()))

        try:
            session.scalars(getUserQuery).one()
        except NoResultFound:
            logger.debug(f"found no User for {member.display_name} (with phone number and api key)")

            return None
        except Exception as error:
            logger.error(f"couldn't fetch User for {member.display_name}", exc_info=error)

            return None

        # noinspection PyTypeChecker
        insertQuery = insert(WhatsappSetting).values(discord_user_id=(select(DiscordUser.id)
                                                                      .where(DiscordUser.user_id == str(member.id))
                                                                      .scalar_subquery()), )

        try:
            session.execute(insertQuery)
            session.commit()
        except Exception as error:
            logger.error(f"couldn't insert new WhatsappSettings for {member.display_name}", exc_info=error)

            return None

        try:
            whatsappSetting = session.scalars(getQuery).one()
        except NoResultFound | Exception as error:
            logger.error(f"couldn't fetch newly inserted WhatsappSetting for {member.display_name}", exc_info=error)

            return None

    except Exception as error:
        logger.error(f"couldn't fetch WhatsappSetting for {member.display_name}", exc_info=error)

        return None

    return whatsappSetting
