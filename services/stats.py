from dataclasses import dataclass, field


@dataclass
class StatsTracker:
    messages_processed: int = 0
    messages_failed: int = 0
    _active_users: set[int] = field(default_factory=set)

    def mark_processed(self, telegram_id: int) -> None:
        self.messages_processed += 1
        self._active_users.add(telegram_id)

    def mark_failed(self, telegram_id: int | None = None) -> None:
        self.messages_failed += 1
        if telegram_id is not None:
            self._active_users.add(telegram_id)

    def snapshot(self) -> dict[str, int]:
        return {
            "messages_processed": self.messages_processed,
            "messages_failed": self.messages_failed,
            "active_users": len(self._active_users),
        }


stats_tracker = StatsTracker()
