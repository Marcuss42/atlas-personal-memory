from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def normalize(value):
    return " ".join(
        value.strip().lower().split()
    )