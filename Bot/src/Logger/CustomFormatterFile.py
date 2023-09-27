import logging
import sys

from Bot.src.Helper.EmailService import send_exception_mail

"""
CUSTOM FORMATTER FOR LOGGING - DONT TOUCH
"""


class CustomFormatterFile(logging.Formatter):
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: format,
        logging.INFO: format,
        logging.WARNING: format,
        logging.ERROR: format,
        logging.CRITICAL: format
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)

        if record.exc_text:
            sys.stderr.write(record.message + "\n")
            sys.stderr.write(record.exc_text + "\n")
            sys.stdout.write(record.message + "\n")
            sys.stdout.write(record.exc_text + "\n")

            send_exception_mail(record.message + "\n" + record.exc_text)

        return formatter.format(record)
