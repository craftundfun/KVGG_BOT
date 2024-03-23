from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import Session

from src.Helper.ReadParameters import Parameters, getParameter
from src.Repository.MessageQueue.Repository.MessageQueueRepository import getUnsentMessagesFromTriggerUser

engine = create_engine(
    f'mysql+mysqlconnector://{getParameter(Parameters.USER)}:{getParameter(Parameters.PASSWORD)}@{getParameter(Parameters.HOST)}/{getParameter(Parameters.NAME)}',
    echo=False)

metadata = MetaData()
metadata.reflect(bind=engine)

with Session(engine) as session:
    print(getUnsentMessagesFromTriggerUser())
