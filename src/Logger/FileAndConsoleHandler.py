import sys
from logging import StreamHandler
from logging.handlers import TimedRotatingFileHandler


class FileAndConsoleHandler(StreamHandler):
    """
    Logs errors in the file in "Logs/log.txt" and the stderr
    """

    def __init__(self, fileHandler: TimedRotatingFileHandler):
        StreamHandler.__init__(self)
        self.fileHandler = fileHandler

    def emit(self, record):
        self.format(record)

        if record.exc_text:
            sys.stderr.write(record.message + "\n")
            sys.stderr.write(record.exc_text)

        self.fileHandler.emit(record)
