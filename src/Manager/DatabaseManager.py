import logging

from sqlalchemy import create_engine, MetaData, Engine
from sqlalchemy.orm import Session

from src.Helper.ReadParameters import getParameter, Parameters

logger = logging.getLogger("KVGG_BOT")
_engine = create_engine(
    f'mysql+mysqlconnector://{getParameter(Parameters.DATABASE_USERNAME)}'
    f':{getParameter(Parameters.DATABASE_PASSWORD)}'
    f'@{getParameter(Parameters.DATABASE_HOST)}'
    f'/{getParameter(Parameters.DATABASE_SCHEMA)}',
    echo=False, pool_recycle=60)
metadata = MetaData()
metadata.reflect(bind=_engine)


def getSession() -> Session | None:
    try:
        return Session(_engine)
    except Exception as error:
        logger.error("could not create new Session", exc_info=error)

        return None


def getEngine() -> Engine:
    return _engine
