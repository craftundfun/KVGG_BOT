import sys
from time import sleep
from typing import Sequence

import requests
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound

from src.Entities.MessageQueue.Entity.MessageQueue import MessageQueue
from src.Helper.ReadParameters import getParameter, Parameters
from src.Manager.DatabaseManager import getSession
from datetime import datetime

MAX_ERRORS = 5
WHATSAPP_API_URL = getParameter(Parameters.WHATSAPP_API_URL)
WHATSAPP_API_KEY = getParameter(Parameters.WHATSAPP_API_KEY)

errors: int = 0
last_error: datetime | None = None

if not WHATSAPP_API_URL or not WHATSAPP_API_KEY:
    raise ValueError("WhatsApp API URL or API Key is not configured properly.")


def increase_error_count():
    global errors, last_error

    errors += 1
    last_error = datetime.now()

    if errors >= MAX_ERRORS:
        print("Maximum error limit reached. Exiting.")

        sys.exit(1)


while True:
    # TODO 15
    sleep(3)
    print("Checking for messages to send...")

    if last_error and (datetime.now() - last_error).total_seconds() >= 120:
        errors = 0
        last_error = None

    session = getSession()

    if not session:
        continue

    query = (
        select(MessageQueue)
        .where(
            MessageQueue.sent_at.is_(None),
            MessageQueue.time_to_sent <= datetime.now(),
        )
    )

    try:
        messages: Sequence[MessageQueue] = session.execute(query).scalars().all()
    except NoResultFound:
        continue
    except Exception as error:
        print(f"Error fetching messages: {error}")
        increase_error_count()

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
        messagesToSend.append({
            "to": message.user.phone_number,
            "message": message.message,
        })

    try:
        response = requests.post(f"{WHATSAPP_API_URL}/send/bulk", json=payload, headers=headers, timeout=5, )

        if response.status_code != 200:
            print(f"Failed to send messages: {response.status_code} - {response.text}")
            increase_error_count()

            continue

        for message in messages:
            message.sent_at = datetime.now()
            session.add(message)

        session.commit()
    except requests.Timeout:
        print("Request timed out.")
        increase_error_count()

        continue
    except Exception as error:
        print(f"Error sending messages: {error}")
        increase_error_count()

        continue
