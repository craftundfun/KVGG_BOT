import sys
from logging import StreamHandler
from logging.handlers import TimedRotatingFileHandler


class Handler(StreamHandler):
    """
    Logs errors in the file in "Logs/log.txt" and the stderr
    """

    def __init__(self, test: TimedRotatingFileHandler):
        StreamHandler.__init__(self)
        self.test = test

    def emit(self, record):
        self.format(record)

        if record.exc_text:
            sys.stderr.write(record.message + "\n")
            sys.stderr.write(record.exc_text)

        self.test.emit(record)
