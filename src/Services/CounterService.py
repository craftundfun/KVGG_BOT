import logging
from pathlib import Path

from discord import Client
from discord import Member
from sqlalchemy import select, insert
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.session import Session

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.Entities.Counter.Entity.Counter import Counter
from src.Entities.Counter.Entity.CounterDiscordMapping import CounterDiscordMapping
from src.Entities.Counter.Repository.CounterRepository import getCounterDiscordMapping
from src.Entities.DiscordUser.Repository.DiscordUserRepository import getDiscordUser
from src.Id.RoleId import RoleId
from src.Manager.DatabaseManager import getSession
from src.Manager.TTSManager import TTSService
from src.Services.ExperienceService import ExperienceService
from src.Services.ProcessUserInput import hasUserWantedRoles, getTagStringFromId
from src.Services.VoiceClientService import VoiceClientService

logger = logging.getLogger("KVGG_BOT")


class CounterService:
    basepath = Path(__file__).parent.parent.parent

    def __init__(self, client: Client):
        self.client = client

        self.voiceClientService = VoiceClientService(self.client)
        self.experienceService = ExperienceService(self.client)
        self.ttsService = TTSService()

    async def createNewCounter(self, name: str, description: str, voiceLine: str, member: Member) -> str:
        """
        Creates a new counter for everyone in the Discord-Database.

        :param name: Name of the new counter
        :param description: Description of the new counter
        :param voiceLine: eventual tts voice line
        :param member: Member who creates the counter
        """
        if not hasUserWantedRoles(member, RoleId.ADMIN, RoleId.MOD):
            logger.debug(f"{member.display_name} has no rights to create counters")

            return "Dir fehlen die Berechtigungen dafür!"

        if name.count(" ") > 0:
            logger.debug("counter name contains white spaces")

            return "Dein Counter-Name darf keine Leerzeichen enthalten."

        if len(name) > 20:
            logger.debug("counter name is longer than 20 characters")

            return "Dein Counter-Name darf nicht länger als 20 Zeichen sein!"

        if len(description) > 100:
            logger.debug("description for new counter too long")

            return "Deine Beschreibung ist zu lang! Bitte benutze maximal 100 Zeichen!"

        if voiceLine and len(voiceLine) > 200:
            logger.debug("voice line too long for new counter")

            return "Deine VoiceLine ist zu lang. Bitte benutze maximal 200 Zeichen!"

        if not (session := getSession()):
            return "Es gab einen Fehler!"

        getQuery = select(Counter.name)

        try:
            counterNames = session.scalars(getQuery).all()
        except Exception as error:
            logger.error("couldn't fetch names of counters from database", exc_info=error)
            session.close()

            return "Es gab einen Fehler!"

        if not counterNames:
            logger.error("counterNames was empty")
            session.close()

            return "Es gab einen Fehler!"

        for counterName in counterNames:
            if counterName.lower() == name.lower():
                logger.debug(f"counter name '{counterName}' does already exist")
                session.close()

                return "Dieser Counter-Name existiert bereits!"

        name = name.lower()

        if voiceLine:
            insertQuery = insert(Counter).values(name=name,
                                                 description=description,
                                                 tts_voice_line=voiceLine, )
        else:
            insertQuery = insert(Counter).values(name=name,
                                                 description=description, )

        try:
            session.execute(insertQuery)
            session.commit()
        except Exception as error:
            logger.error("couldn't insert new counter", exc_info=error)
            session.rollback()
            session.close()

            return "Es gab einen Fehler!"
        else:
            # to notify us per E-Mail
            logger.critical(f"{member.display_name} hat einen neuen Counter erstellt: {name} - {description}")

        session.close()

        return "Dein neuer Counter wurde erstellt!"

    def listAllCounters(self) -> str:
        """
        Returns a list of all counters currently existing
        """
        if not (session := getSession()):
            return "Es gab einen Fehler!"

        getQuery = select(Counter)

        try:
            counters = session.scalars(getQuery).all()
        except Exception as error:
            logger.error("couldnt fetch Counters from database", exc_info=error)
            session.close()

            return "Es gab einen Fehler!"

        if not counters:
            logger.error("couldn't fetch counter from database")

            return "Es gab einen Fehler!"

        answer = "__Es gibt folgende Counter:__\n\n"

        for index, counter in enumerate(counters, 1):
            answer += f"{index}. {counter.name.capitalize()} - {counter.description}\n"

        session.close()

        return answer

    def _getRankingPlace(self, member: Member, counterName: str, session: Session) -> int:
        """
        Returns the current place of the given member for the given counter

        :param member: Member to get the ranking place for
        :param counterName: Counter to get the ranking place for
        """
        # noinspection PyTypeChecker
        getQuery = (select(CounterDiscordMapping)
                    .where(CounterDiscordMapping.counter_id == (select(Counter.id)
                                                                .where(Counter.name == counterName.lower())
                                                                .scalar_subquery()))
                    .order_by(CounterDiscordMapping.value.desc()))
        place = -1

        try:
            # fetch all CounterDiscordMappings for the Counter and find the requestedUser and thus his place in the
            # ranking
            counterMapping = session.scalars(getQuery).all()
        except Exception as error:
            logger.error(f"couldn't fetch all CounterDiscordMappings for Counter: {counterName}", exc_info=error)
        else:
            place = 1

            for mapping in counterMapping:
                if mapping.discord_user.user_id == str(member.id):
                    break

                place += 1

        return place

    async def accessNameCounterAndEdit(self, counterName: str,
                                       requestedUser: Member,
                                       requestingMember: Member,
                                       param: int | None) -> str:
        """
        Answering given Counter from given User or adds (subtracts) given amount

        :param requestedUser: User which counter was requested
        :param counterName: Chosen counter-type
        :param requestingMember: Member who requested the counter
        :param param: Optional amount of time to add / subtract
        :raise ConnectionError: If the database connection cant be established
        :return:
        """
        # whole name with description is given -> split to get name
        counterName = counterName.split(" ")[0]
        answerAppendix = ""

        if not (session := getSession()):
            return "Es gab einen Fehler!"

        logger.debug(f"{requestingMember.display_name} requested {counterName}-Counter")

        if not (dcUserDb := getDiscordUser(requestedUser, session)):
            logger.error(f"couldn't fetch DiscordUser for {requestedUser.display_name}")

            return "Es gab einen Fehler!"

        # noinspection PyTypeChecker
        getQuery = select(Counter).where(Counter.name == counterName.lower())

        try:
            session.scalars(getQuery).one()
        except NoResultFound:
            session.close()

            return "Es gibt diesen Counter (noch) nicht."
        except Exception as error:
            logger.error(f"couldn't fetch counter: {counterName}", exc_info=error)
            session.close()

            return "Es gab einen Fehler!"

        if not (counterDiscordMapping := getCounterDiscordMapping(requestedUser, counterName, session)):
            logger.error(f"no CounterDiscordMapping for {requestedUser.display_name} and {counterName}")
            session.close()

            return "Es gab einen Fehler!"

        if not param:
            return (f"<@{requestedUser.id}> hat einen {counterName.capitalize()}-Counter von "
                    f"{counterDiscordMapping.value}{'' if (place := self._getRankingPlace(requestedUser, counterName, session)) == -1 else ' und landet damit auf Platz ' + str(place)}.")

        try:
            value = int(param)
        except ValueError:
            logger.debug(f"parameter was not convertable to int: {param} by {requestingMember.display_name}")

            return "Dein eingegebener Parameter war ungültig! Bitte gib eine (korrekte) Zahl ein!"

        # user trying to add his own counters
        if int(dcUserDb.user_id) == requestingMember.id:
            # don't allow increasing cookie counter
            if counterName.lower() == "cookie" and value > 0:
                logger.debug(f"{requestingMember.display_name} tried to increase his / her own cookie-counter")

                return "Du darfst deinen eigenen Cookie-Counter nicht erhöhen!"

            # don't allow reducing any counter
            if value < 0:
                logger.debug(f"{requestingMember.display_name} tried to reduce his / her own counter")

                return "Du darfst deinen Counter nicht selber verringern!"

        # only allow privileged users to increase counter by great amounts
        if not hasUserWantedRoles(requestingMember, RoleId.ADMIN, RoleId.MOD) and not -1 <= value <= 1:
            logger.debug(f"{requestingMember.display_name} wanted to edit the Counter: {counterDiscordMapping.counter} "
                         f"to greatly")

            return "Du darfst einen Counter nur um -1 verringern oder +1 erhöhen!"

        counterDiscordMapping.value += value

        # special case for cookie-counter due to xp-boost
        if counterName.lower() == "cookie" and value >= 1:
            try:
                await self.experienceService.grantXpBoost(requestedUser, AchievementParameter.COOKIE)
            except Exception as error:
                logger.error(f"failure to run grantXpBoost for {requestedUser.display_name}", exc_info=error)
            else:
                answerAppendix = "\n\n" + getTagStringFromId(str(requestedUser.id)) + (
                    ", du hast für deinen Keks evtl. einen neuen "
                    "XP-Boost erhalten.")

        # dont decrease to counter into negative
        if counterDiscordMapping.value < 0:
            counterDiscordMapping.value = 0

        tts = None

        if counterDiscordMapping.counter.tts_voice_line and value >= 1:
            try:
                tts = counterDiscordMapping.counter.tts_voice_line.format(name=requestedUser.display_name)
            except KeyError as error:
                logger.error(f"KeyError in '{counterDiscordMapping.counter.tts_voice_line}' von "
                             f"ID: {counterDiscordMapping.counter_id} Counter.", exc_info=error, )
            except Exception as error:
                logger.error(f"something went wrong while creating the TTS for {counterDiscordMapping.counter}",
                             exc_info=error, )

        try:
            session.commit()
        except Exception as error:
            logger.error("couldn't commit changes for CounterService", exc_info=error)
            session.rollback()
            session.close()

            return "Es gab einen Fehler!"

        if requestedUser.voice and tts:
            logger.debug(f"playing TTS for {requestedUser.name}, because {requestingMember.name} increased "
                         f"the {counterName}-Counter")

            if await self.ttsService.generateTTS(tts):
                await self.voiceClientService.play(requestedUser.voice.channel,
                                                   "./data/sounds/tts.mp3",
                                                   None,
                                                   True, )

        return (f"Der {counterName.capitalize()}-Counter von <@{requestedUser.id}> wurde um {value} erhöht! "
                f"<@{requestedUser.id}> hat nun insgesamt {counterDiscordMapping.value} "
                f"{counterName.capitalize()}-Counter"
                f"{'' if (place := self._getRankingPlace(requestedUser, counterName, session)) == -1 else ' und landet damit auf Platz ' + str(place)}."
                + answerAppendix)
