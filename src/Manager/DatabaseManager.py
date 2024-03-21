import logging

from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import Session

from src.Helper.ReadParameters import getParameter, Parameters

logger = logging.getLogger("KVGG_BOT")
_engine = create_engine(
    f'mysql+mysqlconnector://{getParameter(Parameters.USER)}:{getParameter(Parameters.PASSWORD)}@{getParameter(Parameters.HOST)}/{getParameter(Parameters.NAME)}',
    echo=False, )
metadata = MetaData()
metadata.reflect(bind=_engine)


def getSession() -> Session | None:
    logger.debug("returning new Session")

    try:
        return Session(_engine)
    except Exception as error:
        logger.error("could not create new Session", exc_info=error)

        return None
