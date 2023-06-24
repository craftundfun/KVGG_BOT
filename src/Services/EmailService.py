import logging
import smtplib
import string

from email.message import EmailMessage
from src.Id.ExceptionEmailAddresses import ExceptionEmailAddresses
from src.Helper.ReadParameters import getParameter
from src.Helper.ReadParameters import Parameters as param

logger = logging.getLogger("KVGG_BOT")


def send_exception_mail(message: string):
    # check if we are in docker -> if yes send email
    import os
    SECRET_KEY = os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False)
    if not SECRET_KEY:
        return

    exception_recipients = ExceptionEmailAddresses.getValues()

    for exception_recipient in exception_recipients:
        email = EmailMessage()
        email["From"] = "KVGG-Bot-Python"
        email["To"] = exception_recipient
        email["Subject"] = "Test"
        email.set_content(f"Exception Message: {message}\nException Trace: {message}")

        try:
            with smtplib.SMTP_SSL(getParameter(param.EMAIL_HOST), getParameter(param.PORT)) as server:
                server.login(getParameter(param.EMAIL_USER), getParameter(param.EMAIL_PASSWORD))
                server.send_message(email)
        except (Exception, smtplib.SMTPException) as e:
            logger.critical(f"Failed to send the mail to {exception_recipient}: {str(e)}")
