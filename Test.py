from sqlalchemy import create_engine, MetaData
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.Helper.ReadParameters import Parameters, getParameter
from src.Repository.DiscordUsers.DiscordUser import DiscordUser
from src.Repository.Experiences.Experience import Experience
from src.Repository.Users.User import User

engine = create_engine(
    f'mysql+mysqlconnector://{getParameter(Parameters.USER)}:{getParameter(Parameters.PASSWORD)}@{getParameter(Parameters.HOST)}/{getParameter(Parameters.NAME)}',
    echo=False)

metadata = MetaData()
metadata.reflect(bind=engine)

with Session(engine) as session:
    stmt = select(DiscordUser).where(DiscordUser.last_online is not None and DiscordUser.time_online >= 23)

    for user in session.scalars(stmt):
        print(user)

    print("----------------")

    stmt = select(User)

    for user in session.scalars(stmt):
        print(user.roles)

    print("----------------")

    stmt = select(Experience).join(Experience.discord_user).where(DiscordUser.username == "Bjarne")

    for user in session.scalars(stmt):
        print(user)
