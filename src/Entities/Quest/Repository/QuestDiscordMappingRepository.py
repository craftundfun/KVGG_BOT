import logging

from discord import Member
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.DiscordParameters.QuestParameter import QuestDates
from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Entities.Quest.Entity.QuestDiscordMapping import QuestDiscordMapping

logger = logging.getLogger("KVGG_BOT")


def getQuestDiscordMapping(member: Member, session: Session) -> list[QuestDiscordMapping] | None:
    # noinspection PyTypeChecker
    getQuery = (select(QuestDiscordMapping)
                .where(QuestDiscordMapping.discord_id == (select(DiscordUser.id)
                                                          .where(DiscordUser.user_id == str(member.id))
                                                          .scalar_subquery())))

    try:
        currentQuests = session.scalars(getQuery).all()
    except Exception as error:
        logger.error(f"could not fetch quest discord mapping for {member.display_name}", exc_info=error)

        return None

    if len(currentQuests) == (maxLength := (QuestDates.getQuestAmountForDate(QuestDates.DAILY)
                                            + QuestDates.getQuestAmountForDate(QuestDates.WEEKLY)
                                            + QuestDates.getQuestAmountForDate(QuestDates.MONTHLY))):
        logger.debug(f"all quests are already in the database for {member.display_name}")

        return list(currentQuests)

    # circular import
    from src.Services.QuestService import QuestService

    if len(currentQuests) == 0:
        logger.debug("no existing quests for {member.display_name}, creating new ones")

        for questType in [QuestDates.DAILY, QuestDates.WEEKLY, QuestDates.MONTHLY]:
            if not QuestService.insertNewQuestsForMember(member, questType, session):
                logger.error(f"couldn't insert new daily quests for {member.display_name}")

                return None
    elif 0 < len(currentQuests) < maxLength:
        logger.debug("not all quests are in the database for {member.display_name}, creating new missing ones")

        for questType in [QuestDates.DAILY, QuestDates.WEEKLY, QuestDates.MONTHLY]:
            if len([quest for quest in currentQuests if quest.quest.time_type == questType.value]) == 0:
                if not QuestService.insertNewQuestsForMember(member, questType, session):
                    logger.error(f"couldn't insert new {questType} quests for {member.display_name}")

                    return None

    try:
        currentQuests = session.scalars(getQuery).all()
    except Exception as error:
        logger.error(f"couldn't fetch newly created Quests for {member.display_name}", exc_info=error)

        return None
    else:
        logger.debug(f"returning newly created Quests for {member.display_name}")

        return list(currentQuests)
