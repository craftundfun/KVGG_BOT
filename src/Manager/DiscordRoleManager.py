import logging

from discord import Member, Role
from sqlalchemy import delete

from src.Entities.DiscordUser.Repository.DiscordUserRepository import getDiscordUser
from src.Entities.Role.Entity.DiscordRole import DiscordRole
from src.Entities.Role.Entity.DiscordRoleMapping import DiscordRoleMapping
from src.Entities.Role.Repository.DiscordRoleRepository import getDiscordRoleMapping, getDiscordRole
from src.Manager.DatabaseManager import getSession

logger = logging.getLogger("KVGG_BOT")


class DiscordRoleManager:

    def __init__(self):
        pass

    # noinspection PyMethodMayBeStatic
    def updateRoleOfMember(self, before: Member, after: Member):
        if after.bot:
            return

        if before.roles == after.roles:
            return

        if not (session := getSession()):
            return

        if not (dcUserDb := getDiscordUser(after, session)):
            return

        # noinspection PyTypeChecker
        deleteQuery = delete(DiscordRoleMapping).where(DiscordRoleMapping.discord_id == dcUserDb.id)

        try:
            session.execute(deleteQuery)
            session.commit()
        except Exception as error:
            logger.error(f"couldn't delete role mappings for {after.display_name}", exc_info=error)
            session.rollback()

            return
        else:
            logger.debug(f"deleted role mappings for {after.display_name}")

        for role in after.roles:
            if not (discordRoleMapping := getDiscordRoleMapping(role, after, session)):
                logger.error(f"couldn't fetch DiscordRoleMapping for {role} and {after}")

                continue
            else:
                logger.debug(f"found / created {discordRoleMapping}")

        session.close()
        logger.debug(f"updated roles for {after.display_name}")

    # noinspection PyMethodMayBeStatic
    def updateRole(self, before: Role, after: Role):
        if before.name == after.name:
            return

        if not (session := getSession()):
            return

        if not (discordRole := getDiscordRole(before, session)):
            logger.error(f"couldn't fetch DiscordRole for {before}")

            return

        discordRole.name = after.name

        try:
            session.commit()
        except Exception as error:
            logger.error(f"couldn't update DiscordRole for {before}", exc_info=error)
            session.rollback()

            return
        else:
            logger.debug(f"changed {discordRole} from '{before.name}' to '{after.name}'")
        finally:
            session.close()

    # noinspection PyMethodMayBeStatic
    def deleteRole(self, role: Role):
        logger.debug(f"{role} was deleted from the guild")

        if not (session := getSession()):
            return

        if not (discordRole := getDiscordRole(role, session)):
            logger.error(f"couldn't fetch DiscordRole for {role}")

            return

        # noinspection PyTypeChecker
        deleteQuery = delete(DiscordRoleMapping).where(DiscordRoleMapping.role_id == discordRole.id)

        try:
            session.execute(deleteQuery)
            session.commit()
        except Exception as error:
            logger.error(f"couldn't delete role mappings for {role}", exc_info=error)
            session.rollback()

            return
        else:
            logger.debug(f"deleted role mappings for {role}")

        # noinspection PyTypeChecker
        deleteQuery = delete(DiscordRole).where(DiscordRole.id == discordRole.id)

        try:
            session.execute(deleteQuery)
            session.commit()
        except Exception as error:
            logger.error(f"couldn't delete role {role}", exc_info=error)
            session.rollback()

            return
        else:
            logger.debug(f"deleted role {role}")
        finally:
            session.close()
