import logging
import os

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")

_logger = None


def get_logger(name: str = "valcoach") -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    _logger = logging.getLogger(name)
    _logger.setLevel(logging.INFO)

    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        from logging.handlers import TimedRotatingFileHandler
        log_file = os.path.join(LOG_DIR, "valcoach.log")
        file_handler = TimedRotatingFileHandler(log_file, when="midnight", interval=1, backupCount=3, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s"))
        _logger.addHandler(file_handler)
    except Exception:
        pass

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s"))
    _logger.addHandler(console_handler)

    return _logger
