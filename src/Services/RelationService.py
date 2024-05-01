import asyncio
import logging
from enum import Enum

import discord
from discord import ChannelType, Member, Client, VoiceChannel
from sqlalchemy.orm import Session

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.Entities.UserRelation.Repository.DiscordUserRelationRepository import getRelationBetweenUsers
from src.Helper.GetChannelsFromCategory import getVoiceChannelsFromCategoryEnum
from src.Id.Categories import TrackedCategories, UniversityCategory
from src.Id.GuildId import GuildId
from src.Manager.AchievementManager import AchievementService
from src.Manager.DatabaseManager import getSession

logger = logging.getLogger("KVGG_BOT")


class RelationTypeEnum(Enum):
    ONLINE = "online"
    STREAM = "stream"
    UNIVERSITY = "university"
    ACTIVITY = "activity"


# static lock
lock = asyncio.Lock()


class RelationService:

    def __init__(self, client: Client):
        """
        :param client:
        :raise ConnectionError:
        """
        self.client = client

        self.achievementService = AchievementService(self.client)

    async def increaseRelation(self,
                               member_1: Member,
                               member_2: Member,
                               type: RelationTypeEnum,
                               session: Session,
                               value: int = 1):
        """
        Raises a relation of a specific couple. It creates a new relation if possible and if there is none.

        :param member_2:
        :param member_1:
        :param type: Type of the relation
        :param value: Value to be increased
        :param session:
        :return:
        """
        if relation := getRelationBetweenUsers(member_1, member_2, type, session):
            relation.value += value

            # check for grant-able achievements
            match type:
                case RelationTypeEnum.ONLINE:
                    if (relation.value % (AchievementParameter.RELATION_ONLINE_TIME_HOURS.value * 60)) == 0:
                        await self.achievementService.sendAchievementAndGrantBoostForRelation(
                            member_1,
                            member_2,
                            AchievementParameter.RELATION_ONLINE,
                            relation.value,
                        )
                case RelationTypeEnum.STREAM:
                    if (relation.value % (AchievementParameter.RELATION_STREAM_TIME_HOURS.value * 60)) == 0:
                        await self.achievementService.sendAchievementAndGrantBoostForRelation(
                            member_1,
                            member_2,
                            AchievementParameter.RELATION_STREAM,
                            relation.value,
                        )
                case RelationTypeEnum.UNIVERSITY:
                    pass
                case RelationTypeEnum.ACTIVITY:
                    if (relation.value % (AchievementParameter.RELATION_ACTIVITY_TIME_HOURS.value * 60)) == 0:
                        await self.achievementService.sendAchievementAndGrantBoostForRelation(
                            member_1,
                            member_2,
                            AchievementParameter.RELATION_ACTIVITY,
                            relation.value,
                        )
                case _:
                    logger.error(f"undefined enum-entry was reached: {type}")

            try:
                session.commit()
            except Exception as error:
                logger.error(f"couldn't save DiscordUserRelation for {member_1.display_name} and "
                             f"{member_2.display_name}",
                             exc_info=error, )
        else:
            if member_1.bot or member_2.bot:
                logger.warning(f"couldn't fetch DiscordUserRelation for {member_1.display_name} and "
                               f"{member_2.display_name}")
            else:
                logger.error(f"couldn't fetch DiscordUserRelation for {member_1.display_name} and "
                             f"{member_2.display_name}")

    async def increaseAllRelations(self):
        """
        Increases all relations at the same time on this server

        :return:
        """
        whatsappChannels: list[VoiceChannel] = getVoiceChannelsFromCategoryEnum(self.client, TrackedCategories)
        universityChannels: list[VoiceChannel] = getVoiceChannelsFromCategoryEnum(self.client, UniversityCategory)
        allTrackedChannels: list[VoiceChannel] = whatsappChannels + universityChannels

        if not (session := getSession()):
            return

        for channel in self.client.get_guild(GuildId.GUILD_KVGG.value).channels:
            # skip none voice channels
            if channel.type != ChannelType.voice:
                continue

            # skip empty or less than 2 member channels
            if len(channel.members) <= 1:
                # logger.debug("channel %s empty or with less than 2" % channel.name)

                continue

            # skip none tracked channels
            if channel not in allTrackedChannels:
                continue

            members = channel.members
            activityOfMembers: dict = {}

            # for every member with every member
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    logger.debug(f"looking at {members[i].display_name} and {members[j].display_name}")

                    # depending on the channel increase correct relation
                    relation_type = (RelationTypeEnum.ONLINE
                                     if channel in whatsappChannels
                                     else RelationTypeEnum.UNIVERSITY)
                    await self.increaseRelation(members[i], members[j], relation_type, session)

                    # increase streaming relation if both are streaming at the same time
                    if ((members[i].voice.self_stream or members[i].voice.self_video)
                            and (members[j].voice.self_stream or members[j].voice.self_video)):
                        logger.debug(f"{members[i].display_name} and {members[j].display_name} are also "
                                     f"streaming together")
                        await self.increaseRelation(members[i], members[j], RelationTypeEnum.STREAM, session)

                    if members[i].activities and members[i].activities:
                        def cache_activities(member: Member):
                            # don't compare against None;
                            # an empty list will evaluate to True,
                            # thus the caching would be performed every time
                            if not isinstance(activityOfMembers.get(member.id, None), list):
                                activityOfMembers[member.id] = [activity for activity in member.activities
                                                                if not isinstance(activity,
                                                                                  (discord.CustomActivity,
                                                                                   discord.Streaming,))]
                                logger.debug(f"cached activities for {member.display_name}")

                        # if the values are not cached yet, cache them
                        cache_activities(members[i])
                        cache_activities(members[j])

                        # if no allowed activities were found, don't increase the relation
                        if len(activityOfMembers[members[i].id]) == 0 or len(activityOfMembers[members[j].id]) == 0:
                            logger.debug(f"{members[i].display_name} or {members[j].display_name} "
                                         f"had no (allowed) activity")
                            continue

                        logger.debug(f"{members[i].display_name} and {members[j].display_name} are also "
                                     f"playing together")
                        await self.increaseRelation(members[i], members[j], RelationTypeEnum.ACTIVITY, session)
