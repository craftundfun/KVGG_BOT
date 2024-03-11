from sqlalchemy import create_engine, MetaData
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.Helper.ReadParameters import Parameters, getParameter
from src.Repository.DiscordUsers.Quote import Quote

engine = create_engine(
    f'mysql+mysqlconnector://{getParameter(Parameters.USER)}:{getParameter(Parameters.PASSWORD)}@{getParameter(Parameters.HOST)}/{getParameter(Parameters.NAME)}',
    echo=False)

metadata = MetaData()
metadata.reflect(bind=engine)

with Session(engine) as session:
    stmt = select(Quote)

    for item in session.scalars(stmt):
        print(item)
