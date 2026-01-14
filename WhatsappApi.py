import logging.handlers
import sys
from datetime import datetime
from time import sleep
from typing import Sequence

import requests
from sqlalchemy import select, null, or_
from sqlalchemy.exc import NoResultFound

from src.Entities.MessageQueue.Entity.MessageQueue import MessageQueue
from src.Helper.ReadParameters import getParameter, Parameters
from src.Logger.CustomFormatter import CustomFormatter
from src.Logger.CustomFormatterFile import CustomFormatterFile
from src.Manager.DatabaseManager import getSession

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

fileHandler = logging.handlers.TimedRotatingFileHandler(filename="Logs/whatsapp.txt", when="midnight", backupCount=7)
fileHandler.setFormatter(CustomFormatterFile())
fileHandler.setLevel(logging.DEBUG)
logger.addHandler(fileHandler)

consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setFormatter(CustomFormatter())
consoleHandler.setLevel(logging.INFO)
logger.addHandler(consoleHandler)

MAX_ERRORS = 5
BATCH_SIZE = 100
WHATSAPP_API_URL = getParameter(Parameters.WHATSAPP_API_URL)
WHATSAPP_API_KEY = getParameter(Parameters.WHATSAPP_API_KEY)

errors: int = 0
last_error: datetime | None = None

if not WHATSAPP_API_URL or not WHATSAPP_API_KEY:
    logger.error("WhatsApp API URL or API Key not set. Exiting.")
    sys.exit(1)


def increase_error_count():
    global errors, last_error

    errors += 1
    last_error = datetime.now()

    if errors >= MAX_ERRORS:
        logger.error("Maximum error limit reached. Exiting.")

        sys.exit(1)


logger.info("Starting WhatsApp Message Sender Service...")

while True:
    sleep(15)
    logger.debug("Checking for messages to send...")

    if last_error and (datetime.now() - last_error).total_seconds() >= 120:
        errors = 0
        last_error = None

        logger.debug("Resetting error count after cooldown period.")

    session = getSession()

    if not session:
        logger.error("Failed to obtain database session.")

        increase_error_count()

        continue

    with session:
        query = (
            select(MessageQueue)
            .where(
                MessageQueue.sent_at.is_(None),
                or_(MessageQueue.time_to_sent <= datetime.now(), MessageQueue.time_to_sent.is_(None)),
                MessageQueue.error.is_(None),
            )
            .limit(BATCH_SIZE)
        )

        try:
            messages: Sequence[MessageQueue] = session.execute(query).scalars().all()
        except NoResultFound:
            logger.debug("No messages found to send.")

            continue
        except Exception as error:
            logger.error("Error querying messages.", exc_info=error)
            increase_error_count()

            continue

        if not messages:
            logger.debug("No messages to send at this time.")

            continue

        messagesToSend = []
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": WHATSAPP_API_KEY,
        }
        payload = {
            "messages": messagesToSend,
        }

        for message in messages:
            if not (number := message.user.phone_number):
                continue

            messagesToSend.append({
                "to": f"+{number}",
                "message": f"{message.message}\n\n`Ich bin der neue WhatsApp-Bot von KVGG!`",
            })

        try:
            logger.debug("Sending messages to WhatsApp API...")

            response = requests.post(f"{WHATSAPP_API_URL}/send/bulk", json=payload, headers=headers, timeout=5, )

            if response.status_code != 200:
                logger.error(f"Failed to send messages. Status code: {response.status_code}, Response: {response.text}")
                increase_error_count()

                for message in messages:
                    message.error = True
            else:
                for message in messages:
                    message.sent_at = datetime.now()
                    message.error = False

            for message in messages:
                message.time_to_sent = null()

            session.commit()
            logger.info("Messages sent successfully.")
        except requests.Timeout:
            logger.error("Timeout occurred while sending messages to WhatsApp API.")
            increase_error_count()

            continue
        except Exception as error:
            logger.error("Error sending messages to WhatsApp API.", exc_info=error)
            increase_error_count()

            continue
