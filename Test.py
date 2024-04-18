from sqlalchemy.sql import select

from src.Manager.DatabaseManager import getSession
from src.Entities.DiscordUser.Entity.WhatsappSetting import WhatsappSetting

session = getSession()

getQuery = select(WhatsappSetting)

try:
    dcUsersDb = session.scalars(getQuery).all()
except Exception as error:
    print(error)
else:
    print(dcUsersDb[0].suspend_times)

