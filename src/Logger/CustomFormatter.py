import logging
import sys

from src.Helper.EmailService import send_exception_mail

"""
CUSTOM FORMATTER FOR LOGGING - DONT TOUCH
"""


class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    green = "\x1B[32m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: green + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        appendix = record.filename + ":" + str(record.lineno)

        if record.levelno >= logging.WARNING and record.exc_text:
            sys.stderr.write(record.message + "\n")
            sys.stderr.write(record.exc_text + "\n")
            sys.stdout.write(record.message + "\n")
            sys.stdout.write(record.exc_text + "\n")

            send_exception_mail(record.message + f" ({appendix})\n" + record.exc_text)
        elif record.levelno >= logging.WARNING:
            send_exception_mail(record.message + f" ({appendix})\nNo Exception-Text available.")

        return formatter.format(record)
