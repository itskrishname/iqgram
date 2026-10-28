"""Account and runtime configuration. Secrets are never printed."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import importlib
import os


def _integer(name: str, value: object, lo: int, hi: int) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{name} must be an integer') from exc
    if not lo <= out <= hi:
        raise ValueError(f'{name} must be between {lo} and {hi}')
    return out


@dataclass(frozen=True)
class Settings:
    api_id: int = 0
    api_hash: str = ''
    bot_token: str = ''
    allowed_user_ids: str | tuple[int, ...] | list[int] = ''
    data_dir: Path | str = field(default_factory=lambda: Path('./data'))
    max_concurrent_transmissions: int = 8
    queue_workers: int = 2
    delete_after_mirror: bool = False

    @property
    def allowed_ids(self) -> frozenset[int]:
        if isinstance(self.allowed_user_ids, (tuple, list, set)):
            items = self.allowed_user_ids
        else:
            items = [s.strip() for s in str(self.allowed_user_ids).split(',') if s.strip()]
        try:
            out = frozenset(int(x) for x in items)
        except (TypeError, ValueError) as exc:
            raise ValueError('ALLOWED_USER_IDS must be comma-separated integer Telegram user IDs') from exc
        if any(x <= 0 for x in out):
            raise ValueError('ALLOWED_USER_IDS must contain positive integers')
        return out

    @property
    def workdir(self) -> Path:
        return Path(self.data_dir).expanduser().resolve()

    def validate(self, account: str = 'bot') -> None:
        if account not in ('bot', 'user'):
            raise ValueError("account must be 'bot' or 'user'")
        _integer('API_ID', self.api_id, 1, 2**31 - 1)
        if not isinstance(self.api_hash, str) or len(self.api_hash) != 32 or any(c not in '0123456789abcdefABCDEF' for c in self.api_hash):
            raise ValueError('API_HASH must contain 32 hexadecimal characters')
        if account == 'bot' and (not self.bot_token or ':' not in self.bot_token):
            raise ValueError('BOT_TOKEN is required for bot mode')
        _integer('MAX_CONCURRENT_TRANSMISSIONS', self.max_concurrent_transmissions, 1, 32)
        _integer('QUEUE_WORKERS', self.queue_workers, 1, 8)
        self.allowed_ids


def load_settings() -> Settings:
    """Environment values take precedence over optional local config.py."""
    try:
        conf = importlib.import_module('config')
    except ModuleNotFoundError as exc:
        if exc.name != 'config':
            raise
        conf = None

    def get(name: str, default: object = '') -> object:
        return os.environ.get(name, getattr(conf, name, default) if conf is not None else default)

    return Settings(
        api_id=get('API_ID', 0),
        api_hash=str(get('API_HASH')),
        bot_token=str(get('BOT_TOKEN')),
        allowed_user_ids=get('ALLOWED_USER_IDS'),
        data_dir=get('DATA_DIR', './data'),
        max_concurrent_transmissions=_integer('MAX_CONCURRENT_TRANSMISSIONS', get('MAX_CONCURRENT_TRANSMISSIONS', 8), 1, 32),
        queue_workers=_integer('QUEUE_WORKERS', get('QUEUE_WORKERS', 2), 1, 8),
        delete_after_mirror=str(get('DELETE_AFTER_MIRROR', 'false')).lower() in ('1','true','yes','on'),
    )
