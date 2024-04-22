from sqlalchemy.sql import select

from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Manager.DatabaseManager import getSession

session = getSession()

getQuery = select(DiscordUser)

try:
    reminders = session.scalars(getQuery).all()
except Exception as error:
    print(error)
else:
    for reminder in reminders:
        print(reminder.whatsapp_setting)
