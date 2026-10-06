import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def _create_logger(name, filename, level):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.FileHandler(LOG_DIR / filename, encoding="utf-8")
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter(FORMAT))
        logger.addHandler(handler)

    return logger


def get_logger(name):
    return _create_logger(name, "atlas.log", logging.INFO)


def get_debug_logger():
    return _create_logger("atlas-debug", "atlas-debug.log", logging.DEBUG)


def get_error_logger():
    return _create_logger("atlas-error", "atlas-error.log", logging.ERROR)


def _compact(value):
    if value is None:
        return "null"

    if isinstance(value, str):
        return value.replace("\r", "\\r").replace("\n", "\\n")

    return repr(value)


def debug_event(event, **data):
    logger = get_debug_logger()

    parts = [event]

    for key, value in data.items():
        parts.append(f"{key}={_compact(value)}")

    logger.info(" | ".join(parts))


def error_event(event, **data):
    logger = get_error_logger()

    parts = [event]

    for key, value in data.items():
        parts.append(f"{key}={_compact(value)}")

    logger.error(" | ".join(parts))