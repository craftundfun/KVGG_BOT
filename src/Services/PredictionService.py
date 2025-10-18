import logging

import lightgbm as lgb
import pandas as pd
from discord import Client, Member
from pandas import DataFrame
from sklearn.model_selection import train_test_split
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound

from src.DiscordParameters.StatisticsParameter import StatisticsParameter
from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Entities.Statistic.Entity.StatisticLog import StatisticLog
from src.Manager.DatabaseManager import getEngine
from src.Services.ProcessUserInput import getTagStringFromId

logger = logging.getLogger("KVGG_BOT")


class PredictionService:

    def __init__(self, client: Client):
        pass

    async def predict(self, member: Member):
        if member.bot:
            return "Für Bots können keine Vorhersagen getroffen werden."

        try:
            getQuery = (
                select(StatisticLog.created_at, StatisticLog.value)
                .where(
                    StatisticLog.discord_user_id == (
                        select(DiscordUser.id)
                        .where(DiscordUser.user_id == str(member.id))
                        .scalar_subquery()
                    ),
                    StatisticLog.statistic_type == StatisticsParameter.ONLINE.value,
                    StatisticLog.type == StatisticsParameter.DAILY.value,
                )
                .order_by(StatisticLog.created_at.desc())
            )

            dataframe: DataFrame = pd.read_sql_query(getQuery, getEngine())

            data = self._createFeatureSet(dataframe)
            onlineProbability, onlineTime = self._predictNow(data)

            return (f"Basierend auf den bisherigen Daten wird für {getTagStringFromId(member.id)} folgendes "
                    f"vorhergesagt:\n\n"
                    f"- Wahrscheinlichkeit, dass der Nutzer / die Nutzerin heute online ist: **{onlineProbability * 100:.2f}%**\n"
                    f"- Voraussichtliche Onlinezeit (sofern online): **{onlineTime:.2f} Minuten**\n\n"
                    f"-# Es wurden {len(data)} Datensätze seit dem "
                    f"{dataframe.iloc[-1]["created_at"].strftime('%d.%m.%Y')} verwendet.")
        except NoResultFound:
            logger.debug(f"No statistics found for prediction for {member.display_name}")

            return "Dieser Nutzer hat keine Daten zum auswerten."
        except Exception as error:
            logger.error("Could not fetch statistics for prediction", exc_info=error)

            return "Beim Abrufen der Daten ist ein Fehler aufgetreten."

    # noinspection PyMethodMayBeStatic
    def _createFeatureSet(self, data: DataFrame) -> DataFrame:
        """
        Creates features for the prediction model.
        """
        data = data.rename(columns={'created_at': 'date', 'value': 'online_minutes'})
        data = data.sort_values('date', ascending=True)
        # correct date to the previous day, because statistics are created at the beginning of the next day
        data['date'] = data['date'] - pd.Timedelta(days=1)

        for x_days_ago in [1, 2, 3, 7]:
            data[f'{x_days_ago}_days_ago'] = data['online_minutes'].shift(x_days_ago)

        data['rolling_mean_7'] = data['online_minutes'].rolling(7).mean()
        data['rolling_std_7'] = data['online_minutes'].rolling(7).std()
        data['day_of_week'] = data['date'].dt.dayofweek
        data['month'] = data['date'].dt.month

        data = data.dropna()
        return data

    def _predictNow(self, features: pd.DataFrame) -> tuple[float, float]:
        """
        Predicts the online probability and online minutes for the next day.
        """
        feature_cols_binary = [
            '1_days_ago',
            '2_days_ago',
            '3_days_ago',
            '7_days_ago',
            'rolling_mean_7',
            'rolling_std_7',
            'day_of_week',
            'month',
        ]

        ### Binary Classification Model ###
        # add the target variable
        features['was_online'] = (features['online_minutes'] > 0).astype(int)

        X_bin = features[feature_cols_binary]
        y_bin = features['was_online']

        X_train_bin, X_test_bin, y_train_bin, y_test_bin = train_test_split(
            X_bin, y_bin, test_size=0.1, shuffle=False
        )

        model_bin = lgb.LGBMClassifier(
            objective='binary', learning_rate=0.1, n_estimators=200, max_depth=4, n_jobs=-1, verbose=-1,
        )
        model_bin.fit(X_train_bin, y_train_bin)

        ### Regression Model ###
        # only consider days when the user was online, otherwise we have a lot of zeros
        features_active = features[features['online_minutes'] > 0].copy()
        X_reg = features_active[feature_cols_binary]
        y_reg = features_active['online_minutes']

        if not features_active.empty:
            X_train_reg, X_test_reg, y_train_reg, y_test_reg = train_test_split(
                X_reg, y_reg, test_size=0.1, shuffle=False
            )

            model_reg = lgb.LGBMRegressor(
                objective='regression', learning_rate=0.1, n_estimators=200, max_depth=4, n_jobs=-1, verbose=-1,
            )
            model_reg.fit(X_train_reg, y_train_reg)

        last_vals = features['online_minutes'].iloc[-7:].tolist()
        if not last_vals:
            # If there is no data, pad with zeros
            last_vals = [0] * 7
        elif len(last_vals) < 7:
            last_vals = [last_vals[0]] * (7 - len(last_vals)) + last_vals

        X_next = pd.DataFrame({
            '1_days_ago': [features['online_minutes'].iloc[-1]],
            '2_days_ago': [features['online_minutes'].iloc[-2]],
            '3_days_ago': [features['online_minutes'].iloc[-3]],
            '7_days_ago': [last_vals[0]],
            'rolling_mean_7': [features['online_minutes'].where(features['online_minutes'] > 0).tail(7).mean()],
            'rolling_std_7': [features['online_minutes'].where(features['online_minutes'] > 0).tail(7).std()],
            'day_of_week': [(features['date'].iloc[-1] + pd.Timedelta(days=1)).dayofweek],
            'month': [(features['date'].iloc[-1] + pd.Timedelta(days=1)).month]
        })

        prob_online = model_bin.predict_proba(X_next)[0][1]
        # noinspection PyUnboundLocalVariable
        minutes_pred = model_reg.predict(X_next)[0] if not features_active.empty else 0.0

        return prob_online, minutes_pred
