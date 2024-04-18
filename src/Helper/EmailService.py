import logging
import os
import smtplib
from email.message import EmailMessage

from src.Helper.ReadParameters import Parameters as param
from src.Helper.ReadParameters import getParameter
from src.Id.ExceptionEmailAddresses import ExceptionEmailAddresses

logger = logging.getLogger("KVGG_BOT")

funnySubject = [
    "UwU Exception: KVGG-Chan does a super cute oopsie in the world of kawaii programming~",
    "Adorabibble Oopsie-Woopsie Exception: Code-Chan UwU-nexpectedly Trips in the World of Kawaii Programming Nya~",
    "Kawaii Code Catastrophe: UwU-sual Exceptional Adorableness Sends Shockwaves through the Programmer's Heart OwO",
    "STACKTRACE",
    "UwUception: When KVGG-Chan's Cuteness Breaks the Programming Matrix!",
]


def send_exception_mail(message: str):
    # check if we are in docker -> if yes send email
    SECRET_KEY = os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False)

    if not SECRET_KEY:
        return

    exception_recipients = ExceptionEmailAddresses.getValues()
    # TODO subject = funnySubject[random.randint(0, len(funnySubject) - 1)]
    subject = "SQLAlchemy-Stacktrace"

    for exception_recipient in exception_recipients:
        email = EmailMessage()
        email["From"] = "KVGG-Bot-Python"
        email["To"] = exception_recipient
        email["Subject"] = subject
        email.set_content(f"Stacktrace: {message}")

        try:
            with smtplib.SMTP_SSL(getParameter(param.EMAIL_SERVER), int(getParameter(param.EMAIL_PORT))) as server:
                server.login(getParameter(param.EMAIL_USERNAME), getParameter(param.EMAIL_PASSWORD))
                server.send_message(email)
        except Exception as error:
            print("An error occurred while sending an email!\n", error)

            continue
