from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import Session

from src.Helper.ReadParameters import Parameters, getParameter
from src.Repository.User.Entity.User import User

engine = create_engine(
    f'mysql+mysqlconnector://{getParameter(Parameters.USER)}:{getParameter(Parameters.PASSWORD)}@{getParameter(Parameters.HOST)}/{getParameter(Parameters.NAME)}',
    echo=False)

metadata = MetaData()
metadata.reflect(bind=engine)

with Session(engine) as session:
    #getQuery = (select(WhatsappSetting)
    #            .join(User, WhatsappSetting.discord_user_id == User.discord_user_id)
    #            .where(User.phone_number.is_not(None),
    #                   User.api_key_whats_app.is_not(None), ))

    # print(session.scalars(getQuery).all())
    result: list[User] = session.query(User).where(User.phone_number != "", User.api_key_whats_app != "").all()

    for user in result:
        print(f"{user.discord_user.whatsapp_setting}")
