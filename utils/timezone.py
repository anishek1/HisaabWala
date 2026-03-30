"""
HisaabWala - IST Timezone Helpers
Owner: Dev 3

Rule: Store everything in UTC. Convert to IST only at display time or for IST-scoped queries.
"""

from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> datetime:
    """Returns current datetime in IST."""
    return datetime.now(IST)


def now_utc() -> datetime:
    """Returns current datetime in UTC."""
    return datetime.now(timezone.utc)


def today_start_ist() -> datetime:
    """Returns start of today in IST, converted to UTC (for DB queries)."""
    now = datetime.now(IST)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc)


def today_end_ist() -> datetime:
    """Returns end of today in IST, converted to UTC (for DB queries)."""
    now = datetime.now(IST)
    end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    return end.astimezone(timezone.utc)


def format_date_hindi(dt: datetime) -> str:
    """Returns date in DD/MM/YYYY format."""
    ist_dt = dt.astimezone(IST) if dt.tzinfo else dt
    return ist_dt.strftime("%d/%m/%Y")
