import logging
from datetime import UTC, date, datetime

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, limit_per_day: int) -> None:
        self.limit_per_day = limit_per_day
        self._counters: dict[int, tuple[date, int]] = {}

    async def check_and_increment(self, telegram_id: int) -> bool:
        today_utc = datetime.now(UTC).date()
        last_date, count = self._counters.get(telegram_id, (today_utc, 0))

        if last_date != today_utc:
            count = 0

        if count >= self.limit_per_day:
            logger.warning(
                "Rate limit reached.",
                extra={
                    "telegram_id": telegram_id,
                    "limit_per_day": self.limit_per_day,
                    "date": today_utc.isoformat(),
                },
            )
            self._counters[telegram_id] = (today_utc, count)
            return False

        self._counters[telegram_id] = (today_utc, count + 1)
        return True
