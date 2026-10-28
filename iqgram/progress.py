"""Throttled terminal/Telegram progress formatting with average throughput."""
from time import monotonic
from dataclasses import dataclass, field


def size_text(value: int) -> str:
    value = max(0, value)
    if value >= 1024 ** 3:
        return f'{value / 1024 ** 3:.2f} GiB'
    if value >= 1024 ** 2:
        return f'{value / 1024 ** 2:.2f} MiB'
    if value >= 1024:
        return f'{value / 1024:.2f} KiB'
    return f'{value} B'


@dataclass
class ProgressMeter:
    label: str
    interval: float = 1.0
    start: float = field(default_factory=monotonic)
    last_log: float = 0.0
    current: int = 0
    total: int = 0

    def update(self, current: int, total: int) -> str | None:
        self.current = max(0, current)
        self.total = max(0, total)
        now = monotonic()
        if self.current < self.total and now - self.last_log < self.interval:
            return None
        self.last_log = now
        percent = self.current * 100 / self.total if self.total else 0
        rate = self.current / max(0.0001, now - self.start)
        return f'{self.label}: {percent:.1f}% | {size_text(self.current)}/{size_text(self.total)} | {size_text(int(rate))}/s'
