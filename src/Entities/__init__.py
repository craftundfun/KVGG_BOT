from sqlalchemy.orm import configure_mappers

from .Counter.Entity.Counter import Counter
from .Counter.Entity.CounterDiscordMapping import CounterDiscordMapping
from .DiscordUser.Entity.DiscordUser import DiscordUser
from .DiscordUser.Entity.WhatsappSetting import WhatsappSetting
from .DiscordUser.Entity.NotificationSetting import NotificationSetting
from .Experience.Entity.Experience import Experience
from .Game.Entity.DiscordGame import DiscordGame
from .Game.Entity.GameDiscordMapping import GameDiscordMapping
from .History.Entity.Event import Event
from .Meme.Entity.Meme import Meme
from .MessageQueue.Entity.MessageQueue import MessageQueue
from .Newsletter.Entity.Newsletter import Newsletter
from .Newsletter.Entity.NewsletterDiscordMapping import NewsletterDiscordMapping
from .Quest.Entity.Quest import Quest
from .Quest.Entity.QuestDiscordMapping import QuestDiscordMapping
from .Quote.Entity.Quote import Quote
from .Reminder.Entity.Reminder import Reminder
from .Role.Entity.DiscordRole import DiscordRole
from .Role.Entity.DiscordRoleMapping import DiscordRoleMapping
from .Statistic.Entity.StatisticLog import StatisticLog
from .Statistic.Entity.CurrentDiscordStatistic import CurrentDiscordStatistic
# from .Statistic.Entity.AllCurrentServerStats import AllCurrentServerStats -> this is a view
from .User.Entity.User import User
from .UserRelation.Entity.DiscordUserRelation import DiscordUserRelation
from .History.Entity.EventHistory import EventHistory

configure_mappers()
