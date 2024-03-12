from sqlalchemy import create_engine, MetaData
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.Helper.ReadParameters import Parameters, getParameter
from src.Repository.DiscordUsers.DiscordUser import DiscordUser

engine = create_engine(
    f'mysql+mysqlconnector://{getParameter(Parameters.USER)}:{getParameter(Parameters.PASSWORD)}@{getParameter(Parameters.HOST)}/{getParameter(Parameters.NAME)}',
    echo=False)

metadata = MetaData()
metadata.reflect(bind=engine)

with Session(engine) as session:
    stmt = select(DiscordUser)

    for item in session.scalars(stmt):
        print(item)
        print(item.experience)
        print(item.user)
