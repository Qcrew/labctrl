""" """

from pathlib import Path
import sys

import yaml

from loguru import logger

# get logs folder path from labctrl settings.yml
with open(Path.cwd().parent / "settings.yml", "r") as settings:
    LOGSPATH = Path(yaml.safe_load(settings)["logspath"])

logger.remove()  # remove default handlers

# customise logging levels
logger.level("INFO", color="<white>")
logger.level("SUCCESS", color="<green>")
logger.level("WARNING", color="<magenta>")
logger.level("ERROR", color="<red>")

log_record_format = (  # customise log record format
    "<cyan>[{time:YY-MM-DD HH:mm:ss}]</> " "<lvl>{level: <7} [{module}] - {message}</>"
)

# register log sinks with loguru logger
logger.add(
    Path(LOGSPATH) / "session.log",
    format=log_record_format,
    rotation="24 hours",  # current log file closed and new one started every 24 hours
    retention="1 week",  # log files created more than a week ago will be removed
    level="DEBUG",  # save up to "DEBUG" level logs in a log file for debugging
    backtrace=True,
    diagnose=True,
)
logger.add(  # send logged messages to users
    sys.stdout, format=log_record_format, level="INFO", backtrace=False, diagnose=False
)

logger.debug("Logger activated!")
