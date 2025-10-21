import logging

from sqlalchemy import create_engine, MetaData, Engine
from sqlalchemy.orm import Session
from src.Entities.BaseClass import Base

from src.Helper.ReadParameters import getParameter, Parameters

logger = logging.getLogger("KVGG_BOT")
_engine = create_engine(
    f'mysql+mysqlconnector://{getParameter(Parameters.DATABASE_USERNAME)}'
    f':{getParameter(Parameters.DATABASE_PASSWORD)}'
    f'@{getParameter(Parameters.DATABASE_HOST)}'
    f'/{getParameter(Parameters.DATABASE_SCHEMA)}',
    echo=False, pool_recycle=60)

# import the Entities module to register all models and automatically create tables
# noinspection PyUnresolvedReferences
import src.Entities

metadata = Base.metadata
metadata.create_all(bind=_engine, checkfirst=True)
metadata.reflect(bind=_engine)


def getSession() -> Session | None:
    try:
        return Session(_engine)
    except Exception as error:
        logger.error("could not create new Session", exc_info=error)

        return None


def getEngine() -> Engine:
    return _engine
