"""IQGram developer-facing client with bot and user session support."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from .transfer import ProgressCallback, TransferEngine, TransferOptions, TransferResult
from .telethon_adapter import TelethonBackend

class Client:
    """A thin Telegram client with IQGram's own concurrent media scheduler.

    Use as `async with Client('user', api_id, api_hash) as client`.
    For bot authorization, also pass `bot_token=...`.
    """
    def __init__(
        self,
        session: str,
        api_id: int,
        api_hash: str,
        *,
        bot_token: str | None = None,
        options: TransferOptions | None = None,
        _telegram: Any = None,
        _backend: Any = None,
    ) -> None:
        if not isinstance(api_id, int) or api_id <= 0:
            raise ValueError('api_id must be a positive integer')
        if not isinstance(api_hash, str) or not api_hash:
            raise ValueError('api_hash is required')
        if not session:
            raise ValueError('session is required')
        self.bot_token = bot_token
        if _telegram is None:
            try:
                from telethon import TelegramClient
            except ImportError as exc:
                raise ImportError('IQGram live sessions require Telethon: pip install iqgram') from exc
            _telegram = TelegramClient(session, api_id, api_hash)
        self._client = _telegram
        self._backend = _backend if _backend is not None else TelethonBackend(_telegram)
        self._engine = TransferEngine(self._backend, options)

    @property
    def raw(self) -> Any:
        """Underlying MTProto client for all other Telegram methods."""
        return self._client

    async def start(self) -> 'Client':
        if self.bot_token:
            await self._client.start(bot_token=self.bot_token)
        else:
            await self._client.start()
        return self

    async def close(self) -> None:
        await self._client.disconnect()

    async def __aenter__(self) -> 'Client':
        return await self.start()

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()

    async def download(
        self,
        chat: Any,
        message_id: int,
        destination: str | Path,
        *,
        progress: ProgressCallback | None = None,
    ) -> TransferResult:
        message = await self._client.get_messages(chat, ids=message_id)
        if message is None or getattr(message, 'media', None) is None:
            raise ValueError('message not found or has no media')
        file = getattr(message, 'file', None)
        size = getattr(file, 'size', None)
        if not isinstance(size, int) or size <= 0:
            raise ValueError('unknown media size: parallel download requires a document with known size')
        return await self._engine.download(message.media, size, destination, progress=progress)

    async def upload(
        self,
        source: str | Path,
        chat: Any,
        *,
        caption: str | None = None,
        progress: ProgressCallback | None = None,
    ) -> TransferResult:
        return await self._engine.upload(source, chat, caption=caption, progress=progress)
