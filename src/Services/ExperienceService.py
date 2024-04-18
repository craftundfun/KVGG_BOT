from __future__ import annotations

import copy
import logging
import random
import string
from datetime import datetime, timedelta
from typing import Any

from discord import Client, Member
from sqlalchemy import null, select

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.DiscordParameters.ExperienceParameter import ExperienceParameter
from src.Id.GuildId import GuildId
from src.Manager.AchievementManager import AchievementService
from src.Manager.DatabaseManager import getSession
from src.Repository.Experience.Entity.Experience import Experience
from src.Repository.Experience.Repository.ExperienceRepository import getExperience

logger = logging.getLogger("KVGG_BOT")


def isDoubleWeekend(date: datetime) -> bool:
    """
    Returns whether it is currently double-xp-weekend

    :param date:
    :return:
    """
    return date.isocalendar()[1] % 2 == 0 and (date.weekday() == 5 or date.weekday() == 6)


class ExperienceService:

    def __init__(self, client: Client):
        """
        :param client:
        :raise ConnectionError:
        """
        self.client = client

        self.achievementService = AchievementService(self.client)

    def _getDoubleXpWeekendInformation(self) -> string:
        """
        Returns a string with information about this or the upcoming double-xp-weekend

        :return:
        """
        if isDoubleWeekend(datetime.now()):
            return "Dieses Wochenende ist Doppel-XP-Wochenende!"
        else:
            diff: timedelta = self._getDiffUntilNextDoubleXpWeekend()

            return "Das nächste Doppel-XP-Wochenende beginnt in %s Tagen, %s Stunden und %s Minuten." % \
                (diff.days, diff.seconds // 3600, (diff.seconds // 60) % 60)

    def _getDiffUntilNextDoubleXpWeekend(self) -> timedelta:
        """
        Gets the time until the next double-xp-weekend

        :return: Timedelta of duration
        """
        now = datetime.now()  # get current time
        weekday = now.weekday()  # get current weekday
        daysUntilSaturday = (5 - weekday) % 7  # calculate days until saturday
        nextSaturday = now + timedelta(days=daysUntilSaturday)  # get date of next saturday
        nextSaturday = nextSaturday.replace(hour=0, minute=0, second=0, microsecond=0)  # set to midnight

        if isDoubleWeekend(nextSaturday):
            return nextSaturday - now
        else:
            nextNextSaturday = now + timedelta(days=daysUntilSaturday + 7)  # get next weeks saturday
            nextNextSaturday = nextNextSaturday.replace(hour=0, minute=0, second=0, microsecond=0)

            return nextNextSaturday - now

    async def grantXpBoost(self, member: Member, kind: AchievementParameter):
        """
        Grants the member the specified xp-boost

        :param member: Member who earned the boost
        :param kind: Kind of boost
        :raise ConnectionError: If the database connection cant be established
        """
        # import and instantiate here due to avoiding circular import
        from src.Manager.NotificationManager import NotificationService
        notificationService = NotificationService(self.client)

        if not isinstance(kind.value, str):
            logger.error("false argument given")

            return

        if not (session := getSession()):
            return

        if not (xp := getExperience(member, session)):
            logger.debug(f"couldn't fetch xp for {member.display_name}")

            return

        match kind:
            case AchievementParameter.ONLINE:
                boost = {
                    'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_ONLINE.value,
                    'remaining': ExperienceParameter.XP_BOOST_ONLINE_DURATION.value,
                    'description': ExperienceParameter.DESCRIPTION_ONLINE.value,
                }
            case AchievementParameter.STREAM:
                boost = {
                    'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_STREAM.value,
                    'remaining': ExperienceParameter.XP_BOOST_STREAM_DURATION.value,
                    'description': ExperienceParameter.DESCRIPTION_STREAM.value,
                }
            case AchievementParameter.RELATION_ONLINE:
                boost = {
                    'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_RELATION_ONLINE.value,
                    'remaining': ExperienceParameter.XP_BOOST_RELATION_ONLINE_DURATION.value,
                    'description': ExperienceParameter.DESCRIPTION_RELATION_ONLINE.value,
                }
            case AchievementParameter.RELATION_STREAM:
                boost = {
                    'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_RELATION_STREAM.value,
                    'remaining': ExperienceParameter.XP_BOOST_RELATION_STREAM_DURATION.value,
                    'description': ExperienceParameter.DESCRIPTION_RELATION_STREAM.value,
                }
            case AchievementParameter.COOKIE:
                if lastBoost := xp.last_cookie_boost:
                    if ((interval := (datetime.now() - lastBoost)).days
                            < ExperienceParameter.WAIT_X_DAYS_BEFORE_NEW_COOKIE_BOOST.value
                            and interval.seconds
                            < ExperienceParameter.WAIT_X_DAYS_BEFORE_NEW_COOKIE_BOOST.value * 24 * 60 * 60):
                        logger.debug("cant grant new cookie boost, time was not passed")

                        return

                boost = {
                    'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_COOKIE.value,
                    'remaining': ExperienceParameter.XP_BOOST_COOKIE_DURATION.value,
                    'description': ExperienceParameter.DESCRIPTION_COOKIE.value,
                }
                xp.last_cookie_boost = datetime.now()
            case AchievementParameter.DAILY_QUEST:
                boost = {
                    'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_DAILY_QUEST.value,
                    'remaining': ExperienceParameter.XP_BOOST_DAILY_QUEST_DURATION.value,
                    'description': ExperienceParameter.DESCRIPTION_DAILY_QUEST.value,
                }
            case AchievementParameter.WEEKLY_QUEST:
                boost = {
                    'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_WEEKLY_QUEST.value,
                    'remaining': ExperienceParameter.XP_BOOST_WEEKLY_QUEST_DURATION.value,
                    'description': ExperienceParameter.DESCRIPTION_WEEKLY_QUEST.value,
                }
            case AchievementParameter.MONTHLY_QUEST:
                boost = {
                    'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_MONTHLY_QUEST.value,
                    'remaining': ExperienceParameter.XP_BOOST_MONTHLY_QUEST_DURATION.value,
                    'description': ExperienceParameter.DESCRIPTION_MONTHLY_QUEST.value,
                }
            case AchievementParameter.BEST_MEME_OF_THE_MONTH:
                boost = {
                    'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_BEST_MEME.value,
                    'remaining': ExperienceParameter.XP_BOOST_BEST_MEME_DURATION.value,
                    'description': ExperienceParameter.DESCRIPTION_BEST_MEME.value,
                }
            case AchievementParameter.WORST_MEME_OF_THE_MONTH:
                boost = {
                    'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_WORST_MEME.value,
                    'remaining': ExperienceParameter.XP_BOOST_WORST_MEME_DURATION.value,
                    'description': ExperienceParameter.DESCRIPTION_WORST_MEME.value,
                }
            case AchievementParameter.TIME_PLAYED:
                boost = {
                    'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_TIME_PLAYED.value,
                    'remaining': ExperienceParameter.XP_BOOST_TIME_PLAYED_DURATION.value,
                    'description': ExperienceParameter.DESCRIPTION_TIME_PLAYED.value,
                }
            case _:
                logger.critical("undefined enum entry was reached")

                return

        if xp.xp_boosts_inventory:
            inventory = copy.deepcopy(xp.xp_boosts_inventory)

            if len(inventory) >= ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value:
                logger.debug("cant grant boost, too many inactive xp boosts")

                await notificationService.informAboutXpBoostInventoryLength(member, len(inventory))

                return
        else:
            inventory = []

        inventory.append(boost)
        xp.xp_boosts_inventory = inventory

        try:
            session.commit()
        except Exception as error:
            logger.error(f"couldn't save new xp boost to database for {member.display_name}", exc_info=error)
            session.rollback()

            return
        else:
            await notificationService.informAboutXpBoostInventoryLength(member, len(inventory))

            logger.debug(f"saved granted boost to database for {member.display_name}")
        finally:
            session.close()

    def spinForXpBoost(self, member: Member) -> str:
        """
        Xp-Boost-Spin for member

        :param member: Member, who started the spin
        :raise ConnectionError: If the database connection cant be established
        :return:
        """
        logger.debug(f"{member.display_name} requested xp-spin")

        if not (session := getSession()):  # TODO outside
            return "Es gab einen Fehler!"

        if not (xp := getExperience(member, session)):
            logger.error(f"couldn't fetch Experience for {member.display_name}")

            return "Es gab einen Fehler!"

        inventory = xp.xp_boosts_inventory

        if not inventory:
            inventory = []

        if len(inventory) >= ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value:
            logger.debug(f"full inventory, cant spin for {member.display_name}")

            return "Dein Inventar ist voll! Benutze erst einen oder mehrere XP-Boosts!"

        lastXpSpinTime = xp.last_spin_for_boost

        if lastXpSpinTime:
            difference: timedelta = datetime.now() - lastXpSpinTime
            days = difference.days
            hours, remainingSeconds = divmod(difference.seconds, 3600)
            minutes, remainingSeconds = divmod(remainingSeconds, 60)  # why Python, why?

            # cant spin again -> still on cooldown
            if days < ExperienceParameter.WAIT_X_DAYS_BEFORE_NEW_SPIN.value:
                remainingDays = ExperienceParameter.WAIT_X_DAYS_BEFORE_NEW_SPIN.value - days - 1
                remainingHours = 23 - hours
                remainingMinutes = 59 - minutes
                remainingSeconds = 59 - remainingSeconds

                logger.debug(f"cant spin, still on cooldown for {member.display_name}")

                if days == 6 and hours == 23 and minutes == 59:
                    return f"Du darfst noch nicht wieder drehen! Versuche es in {remainingSeconds} Sekunden wieder!"

                return (f"Du darfst noch nicht wieder drehen! Versuche es in {remainingDays} Tag(en), "
                        f"{remainingHours} Stunde(n) und {remainingMinutes} Minute(n) wieder!")

        # win
        if random.randint(0, (100 / ExperienceParameter.SPIN_WIN_PERCENTAGE.value)) == 1:
            logger.debug(f"{member.display_name} won a xp boost")

            boost = {
                'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_SPIN.value,
                'remaining': ExperienceParameter.XP_BOOST_SPIN_DURATION.value,
                'description': ExperienceParameter.DESCRIPTION_SPIN.value,
            }

            inventory.append(boost)

            xp.xp_boosts_inventory = inventory
            xp.last_spin_for_boost = datetime.now()
            xp.time_to_send_spin_reminder = (datetime.now()
                                             + timedelta(days=ExperienceParameter.WAIT_X_DAYS_BEFORE_NEW_SPIN.value))

            try:
                session.commit()
            except Exception as error:
                logger.error(f"couldn't commit changes for {xp} and {member.display_name}", exc_info=error)
                session.rollback()
                session.close()

                return "Es gab einen Fehler"
            else:
                return (f"Du hast einen XP-Boost gewonnen!!! Für "
                        f"{int(ExperienceParameter.XP_BOOST_SPIN_DURATION.value / 60)} Stunde(n) bekommst du "
                        f"{ExperienceParameter.XP_BOOST_MULTIPLIER_SPIN.value}-Fach XP! Setze ihn über dein Inventar "
                        f"ein!")
        else:
            logger.debug(f"{member.display_name} did not win xp boost")

            days = ExperienceParameter.WAIT_X_DAYS_BEFORE_NEW_SPIN.value
            xp.last_spin_for_boost = datetime.now()
            xp.time_to_send_spin_reminder = (datetime.now()
                                             + timedelta(days=ExperienceParameter.WAIT_X_DAYS_BEFORE_NEW_SPIN.value))

            try:
                session.commit()
            except Exception as error:
                logger.error(f"couldn't commit changes for {xp} and {member.display_name}", exc_info=error)
                session.rollback()
                session.close()

                return "Es gab einen Fehler!"

            return f"Du hast leider nichts gewonnen! Versuche es in {days} Tagen nochmal!"

    async def runExperienceReminder(self):
        """
        Searches the database for open xp-spin reminders and notifies the member
        """
        if not (session := getSession()):  # TODO outside
            return

        # noinspection PyTypeChecker
        # noinspection PyUnresolvedReferences
        getQuery = select(Experience.discord_user).where(Experience.time_to_send_spin_reminder.is_not(None),
                                                         Experience.time_to_send_spin_reminder <= datetime.now(), )

        try:
            xps = session.scalars(getQuery).all()
        except Exception as error:
            logger.error("couldn't fetch Experiences", exc_info=error)
            session.close()

            return

        if not xps:
            logger.debug("no xp-spin reminders to run")

            return

        if not (guild := self.client.get_guild(GuildId.GUILD_KVGG.value)):
            logger.error("couldn't fetch guild")

            return

        # circular import
        from src.Manager.NotificationManager import NotificationService

        notificationService = NotificationService(self.client)

        for xp in xps:
            if not (member := guild.get_member(int(xp.discord_user.user_id))):
                logger.error(f"couldn't fetch member for DiscordUser: {xp.discord_user}")

                continue

            await notificationService.sendXpSpinNotification(member, "Du kannst wieder den XP-Spin nutzen!")
            logger.debug(f"informed DiscordUser: {xp.discord_user} about the xp-spin")

            xp.time_to_send_spin_reminder = null()

            try:
                session.commit()
            except Exception as error:
                logger.error(f"couldn't commit {xp}", exc_info=error)
                session.rollback()

                continue
            else:
                logger.debug(f"updated {xp}")

        session.close()

    def handleXpRequest(self, requestingMember: Member, requestedMember: Member) -> str:
        """
        Handles the XP-Request of the given tag

        :param requestedMember: Tag of the requested user
        :param requestingMember: Member, who called the command
        :raise ConnectionError: If the database connection can't be established
        :return: string - answer
        """
        logger.debug(f"{requestingMember.display_name} requested xp for {requestedMember.display_name}")

        if not (session := getSession()):  # TODO outside
            return "Es gab einen Fehler!"

        if not (xp := getExperience(requestedMember, session)):
            logger.error(f"couldn't fetch Experience for {requestedMember.display_name}")

            return "Es gab einen Fehler!"

        reply = f"<@{requestedMember.id}> hat bereits {'{:,}'.format(xp.xp_amount).replace(',', '.')} XP gefarmt!\n\n"
        reply += self._getDoubleXpWeekendInformation()

        logger.debug(f"replying xp amount for {requestedMember.display_name} by {requestingMember.display_name}")
        session.close()

        return reply

    def handleXpInventory(self, member: Member, action: str, row: str = None) -> str:
        """
        Handles the XP-Inventory

        :param member: Member, who the inventory belongs to
        :param action: Action the user wants to perform with his inventory
        :param row: Optional row to choose boost from
        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        logger.debug(f"{member.display_name} requested xp-inventory")

        if not (session := getSession()):  # TODO outside
            return "Es gab einen Fehler!"

        if not (xp := getExperience(member, session)):
            logger.error(f"couldn't fetch Experience for {member.display_name}")
            session.close()

            return "Es gab einen Fehler!"

        # list all boosts in the (active) inventory
        if action == 'list':
            logger.debug(f"list-action used by {member.display_name}")

            reply = ""

            if not xp.xp_boosts_inventory:
                logger.debug(f"no boosts in inventory for {member.display_name}")

                reply += "**__Du hast keine XP-Boosts in deinem Inventar!__**"

                if xp.active_xp_boosts:
                    reply += "\n\n**__Du hast folgende aktive XP-Boosts__**:\n"
                    inventory: list[dict[str, Any]] = xp.active_xp_boosts

                    for index, item in enumerate(inventory, start=1):
                        reply += (f"{index}. {item['description']}-Boost, der noch für {item['remaining']} Minuten "
                                  f"{item['multiplier']}-Fach XP gibt\n")

                session.close()

                return reply

            logger.debug(f"list all current and active boosts for {member.display_name}")

            reply = "**__Du hast folgende XP-Boosts in deinem Inventar__**:\n"
            inventory: list[dict[str, Any]] | None = xp.xp_boosts_inventory

            for index, item in enumerate(inventory, start=1):
                reply += (f"{index}. {item['description']}-Boost, für {item['remaining']} Minuten "
                          f"{item['multiplier']}-Fach XP\n")

            reply = reply.rstrip("\n")

            if xp.active_xp_boosts:
                reply += "\n\n**__Du hast folgende aktive XP-Boosts__**:\n"
                activeInventory: list[dict[str, Any]] = xp.active_xp_boosts

                for index, item in enumerate(activeInventory, start=1):
                    reply += (f"{index}. {item['description']}-Boost, der noch für {item['remaining']} Minuten "
                              f"{item['multiplier']}-Fach XP gibt\n")

                reply = reply.rstrip("\nf")

            reply += "\n\nMit `/xp_inventory use zeile:1 | all` kannst du einen oder mehrere XP-Boost einsetzen!"

            session.close()

            return reply
        # !inventory use
        else:
            logger.debug(f"use-action used by {member.display_name}")

            # no xp boosts available
            if not xp.xp_boosts_inventory:
                logger.debug(f"no boosts in inventory for {member.display_name}")
                session.close()

                return "Du hast keine XP-Boosts in deinem Inventar!"

            # too many xp boosts are active, cant activate another one
            if xp.active_xp_boosts and len(xp.active_xp_boosts) >= ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value:
                logger.debug(f"too many boosts active for {member.display_name}")
                session.close()

                return "Du hast zu viele aktive XP-Boosts! Warte bis einer ausgelaufen ist und probiere " \
                       "es erneut!"

            # inventory use all
            if row == 'all':
                logger.debug(f"use all boosts for {member.display_name}")
                # list to keep track of which boosts will be used
                usedBoosts = []

                currentInventory: list[dict[str, Any]] | None \
                    = copy.deepcopy(xp.xp_boosts_inventory) if xp.xp_boosts_inventory else None
                activeBoosts: list[dict[str, Any]] | None \
                    = copy.deepcopy(xp.active_xp_boosts) if xp.active_xp_boosts else None
                maxValue: int = ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value

                # empty active boosts and fewer then max boosts => can use all boosts at once
                if currentInventory and not activeBoosts and len(currentInventory) <= maxValue:
                    logger.debug(f"no active boosts, all will fit for {member.display_name}")

                    xp.active_xp_boosts = copy.deepcopy(xp.xp_boosts_inventory)
                    usedBoosts = copy.deepcopy(xp.xp_boosts_inventory)
                    xp.xp_boosts_inventory = None
                # xp boosts can fit into active
                elif currentInventory and activeBoosts and (len(currentInventory) + len(activeBoosts) <= maxValue):
                    logger.debug(f"active boosts present, but new ones fit for {member.display_name}")

                    usedBoosts = copy.deepcopy(xp.xp_boosts_inventory)
                    inventory: list[dict[str, Any]] | None = copy.deepcopy(xp.xp_boosts_inventory)
                    activeBoosts: list[dict[str, Any]] = copy.deepcopy(xp.active_xp_boosts)
                    xp.active_xp_boosts = activeBoosts + inventory
                    xp.xp_boosts_inventory = None
                # not all xp-boosts fit into active ones
                else:
                    logger.debug(f"active boosts, choose only fitting ones for {member.display_name}")

                    if not activeBoosts:
                        activeBoosts = []

                    currentPosInInventory = 0
                    numXpBoosts = len(activeBoosts)
                    inventoryAfter: list[dict[str, Any]] = copy.deepcopy(xp.xp_boosts_inventory)

                    while (numXpBoosts < ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value
                           and currentPosInInventory < len(currentInventory)):
                        currentBoost = currentInventory[currentPosInInventory]

                        usedBoosts.append(currentBoost)
                        activeBoosts.append(currentBoost)
                        inventoryAfter.remove(currentBoost)

                        currentPosInInventory += 1
                        numXpBoosts += 1

                    xp.xp_boosts_inventory = inventoryAfter if len(inventoryAfter) > 0 else None
                    xp.active_xp_boosts = activeBoosts

                answer = "**__Alle (möglichen) XP-Boosts wurden eingesetzt:__**\n"

                for index, boost in enumerate(usedBoosts, start=1):
                    answer += (f"{index}. {boost['description']}-Boost, der für {boost['remaining']} Minuten "
                               f"{boost['multiplier']}-Fach XP gibt\n")

            # !inventory use 1
            else:
                logger.debug(f"using boosts in specific row for {member.display_name}")

                # inventory empty
                if not xp.xp_boosts_inventory:
                    logger.debug(f"no boosts in inventory for {member.display_name}")

                    return "Du hast keine XP-Boosts in deinem Inventar!"
                # active inventory full
                elif (xp.active_xp_boosts
                      and len(xp.active_xp_boosts) >= ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value):
                    logger.debug(f"too many active boosts for {member.display_name}")
                    session.close()

                    return "Du hast zu viele aktive XP-Boosts! Warte bis einer ausgelaufen ist und probiere es erneut!"

                try:
                    if not row:
                        raise ValueError
                    row = int(row)
                except ValueError:
                    logger.debug(f"entered row was no number by {member.display_name}")
                    session.close()

                    return "Bitte gib eine korrekte Zeilennummer ein!"

                inventory: list[dict[str, Any]] = copy.deepcopy(xp.xp_boosts_inventory)

                if len(inventory) >= row > 0:
                    chosenXpBoost = inventory[row - 1]

                    if not xp.active_xp_boosts:
                        activeXpBoosts: list[dict[str, Any]] = []
                    else:
                        activeXpBoosts: list[dict[str, Any]] = copy.deepcopy(xp.active_xp_boosts)

                    inventory.remove(chosenXpBoost)
                    activeXpBoosts.append(chosenXpBoost)

                    if not inventory:
                        xp.xp_boosts_inventory = None
                    else:
                        xp.xp_boosts_inventory = inventory

                    xp.active_xp_boosts = activeXpBoosts

                    answer = (f"Dein XP-Boost wurde eingesetzt! Für die nächsten {chosenXpBoost['remaining']} "
                              f"Minuten bekommst du {chosenXpBoost['multiplier']}-Fach XP!")
                else:
                    logger.debug(f"number out of range for {member.display_name}")
                    session.close()

                    return "Deine Eingabe war ungültig!"

        # otherwise the string "null" would be in the database, not <null>
        if xp.xp_boosts_inventory is None:
            xp.xp_boosts_inventory = null()

        if xp.active_xp_boosts is None:
            xp.active_xp_boosts = null()

        try:
            session.commit()
        except Exception as error:
            logger.error(f"couldn't commit changes for {xp} and {member.display_name}", exc_info=error)
            session.rollback()

            return "Es gab einen Fehler!"
        else:
            return answer
        finally:
            session.close()

    async def addExperience(self, experienceParameter: int, member: Member = None):
        """
        Adds the given amount of xp to the given user

        :param member: Optional Member if DiscordUser is not used
        :param experienceParameter: Amount of xp
        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        logger.debug(f"{member.display_name} gets XP")

        if not (session := getSession()):  # TODO outside
            return

        xp = getExperience(member, session)

        if not xp:
            logger.error("couldn't fetch experience")

            return

        xpAmountBefore = xp.xp_amount
        toBeAddedXpAmount = experienceParameter

        if xp.active_xp_boosts:
            logger.debug("multiply xp with active boosts")

            for boost in xp.active_xp_boosts:
                # don't add the base experience everytime
                toBeAddedXpAmount += experienceParameter * boost['multiplier'] - experienceParameter

        if toBeAddedXpAmount == experienceParameter:
            if isDoubleWeekend(datetime.now()):
                xp.xp_amount = xpAmountBefore + experienceParameter * ExperienceParameter.XP_WEEKEND_VALUE.value
            else:
                xp.xp_amount = xpAmountBefore + experienceParameter
        else:
            if isDoubleWeekend(datetime.now()):
                xp.xp_amount = (xpAmountBefore + toBeAddedXpAmount
                                + experienceParameter * ExperienceParameter.XP_WEEKEND_VALUE.value)
            else:
                xp.xp_amount = xpAmountBefore + toBeAddedXpAmount

        # convert to int because of worst meme boost
        xp.xp_amount = int(xp.xp_amount)

        try:
            session.commit()
        except Exception as error:
            logger.error(f"error while committing increased experience for {member.display_name}", exc_info=error)

        # 99 mod 10 > 101 mod 10 -> achievement for 100
        if (xpAmountBefore % AchievementParameter.XP_AMOUNT.value
                > xp.xp_amount % AchievementParameter.XP_AMOUNT.value):
            await (self
                   .achievementService
                   .sendAchievementAndGrantBoost(member,
                                                 AchievementParameter.XP,
                                                 (xp.xp_amount -
                                                  (xp.xp_amount % AchievementParameter.XP_AMOUNT.value))))

        session.close()

    # TODO test
    def reduceXpBoostsTime(self, member: Member):
        """
        Reduces the active boosts time from the given member.

        :param member:
        """
        if not (session := getSession()):
            return

        if not (xp := getExperience(member, session)):
            logger.error(f"couldn't fetch Experience for {member.display_name}")
            session.close()

            return

        if not xp.active_xp_boosts:
            logger.debug(f"no boosts to reduce for {member.display_name}")
            session.close()

            return

        boosts = copy.deepcopy(xp.active_xp_boosts)
        editedBoosts = []

        for boost in boosts:
            boost['remaining'] = boost['remaining'] - 1

            if boost['remaining'] > 0:
                editedBoosts.append(boost)

        if len(editedBoosts) == 0:
            boosts = None
        else:
            boosts = editedBoosts

        xp.active_xp_boosts = boosts

        try:
            session.commit()
        except Exception as error:
            logger.error(f"couldn't save Experience for {member.display_name}", exc_info=error)
            session.rollback()
            session.close()

            return

        session.close()
        logger.debug(f"reduced xp boosts for {member.display_name}")

        return
