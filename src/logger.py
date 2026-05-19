import logging
import os

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")

_logger = None


class _SafeFileHandler(logging.Handler):
    """File handler that gracefully handles rotation failures on Windows."""
    def __init__(self, filename, encoding="utf-8"):
        super().__init__()
        self.base_filename = filename
        self._encoding = encoding
        self._stream = None

    def _open(self):
        try:
            os.makedirs(os.path.dirname(self.base_filename), exist_ok=True)
        except Exception:
            pass
        return open(self.base_filename, "a", encoding=self._encoding)

    def emit(self, record):
        if self._stream is None:
            try:
                self._stream = self._open()
            except Exception:
                return
        try:
            msg = self.format(record)
            self._stream.write(msg + "\n")
            self._stream.flush()
        except Exception:
            pass


def get_logger(name: str = "valcoach") -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    _logger = logging.getLogger(name)
    _logger.setLevel(logging.INFO)

    try:
        log_file = os.path.join(LOG_DIR, "valcoach.log")
        file_handler = _SafeFileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s"))
        _logger.addHandler(file_handler)
    except Exception:
        pass

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s"))
    _logger.addHandler(console_handler)

    return _logger
