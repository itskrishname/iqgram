"""IQGram developer-facing client with bot and user session support."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import os
import time
import asyncio
import tempfile
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
        self._owns_client = True

    @classmethod
    def from_telethon(
        cls,
        telegram: Any,
        *,
        options: TransferOptions | None = None,
    ) -> 'Client':
        """Attach to an already connected Telethon client without owning its lifecycle.

        The bot/application remains responsible for start/disconnect. This is
        intended for existing Telethon bots and user clients, not Pyrogram or
        Aiogram objects (those require their own IQGram MTProto session).
        """
        if (telegram is None or
            any(not callable(getattr(telegram, method, None)) for method in
                ('get_messages', 'iter_download', 'send_file'))):
            raise TypeError('from_telethon requires an existing Telethon TelegramClient')
        result = cls.__new__(cls)
        result.bot_token = None
        result._client = telegram
        result._backend = TelethonBackend(telegram)
        result._engine = TransferEngine(result._backend, options)
        result._owns_client = False
        return result

    @property
    def raw(self) -> Any:
        """Underlying MTProto client for all other Telegram methods."""
        return self._client

    async def start(self) -> 'Client':
        if not self._owns_client:
            connected = getattr(self._client, 'is_connected', None)
            if callable(connected) and not connected():
                raise RuntimeError('External Telethon client must be already connected')
            return self
        if self.bot_token:
            await self._client.start(bot_token=self.bot_token)
        else:
            await self._client.start()
        return self

    async def close(self) -> None:
        if self._owns_client:
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
        profile: bool = False,
    ) -> TransferResult:
        message = await self._client.get_messages(chat, ids=message_id)
        if message is None or getattr(message, 'media', None) is None:
            raise ValueError('message not found or has no media')
        file = getattr(message, 'file', None)
        size = getattr(file, 'size', None)
        if isinstance(size, int) and size > 0:
            return await self._engine.download(message.media, size, destination, progress=progress, profile=profile)
        # Telegram PhotoSize and some other supported media may not expose
        # a trustworthy length; use Telethon's verified media downloader.
        if getattr(message, 'photo', None) is None and getattr(message, 'document', None) is None:
            raise TypeError('message contains no downloadable file media (poll, geo, etc. are not files)')
        target = Path(destination)
        if target.exists():
            raise FileExistsError(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        start = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix='.iqgram-media-', dir=target.parent) as td:
            # A temporary directory safely contains any extension selected by Telethon.
            tmp = Path(td) / ('media' + (target.suffix or '.bin'))
            received = await self._client.download_media(message, file=str(tmp))
            if received is None:
                raise ValueError('Telegram did not return downloadable media')
            received_path = Path(received)
            if received_path.parent.resolve() != Path(td).resolve():
                raise ValueError('Telegram returned a path outside of the private download directory')
            if not received_path.is_file() or received_path.stat().st_size == 0:
                raise ValueError('Telegram returned empty or missing media')
            elapsed = time.perf_counter() - start
            count = received_path.stat().st_size
            if progress is not None:
                from .transfer import Progress
                result = progress(Progress(count, count, elapsed, 'download'))
                import inspect
                if inspect.isawaitable(result):
                    await result
            # Atomic no-replace publication only after successful callback.
            await asyncio.to_thread(os.link, received_path, target)
            return TransferResult(count, elapsed, 'download', target)

    async def upload(
        self,
        source: str | Path,
        chat: Any,
        *,
        caption: str | None = None,
        progress: ProgressCallback | None = None,
        media_kind: str = "document",
    ) -> TransferResult:
        return await self._engine.upload(source, chat, caption=caption, progress=progress, media_kind=media_kind)

    async def reuse_media(
        self,
        source_chat: Any,
        message_id: int,
        destination_chat: Any,
        *,
        caption: str | None = None,
    ) -> Any:
        """Resend permitted existing Telegram file media without VPS download/upload.

        This is a server-side media reference operation, NOT a measured
        byte-transfer speedup. Protected and non-file messages are rejected.
        """
        message = await self._client.get_messages(source_chat, ids=message_id)
        if message is None or getattr(message, 'media', None) is None:
            raise ValueError('source message has no media')
        if getattr(message, 'noforwards', False):
            raise PermissionError('source media is protected from forwarding/reuse')
        # Telegram can only reuse existing photo/document file references.
        # For other types call the underlying Telethon API explicitly.
        media = message.media
        if not (getattr(message, 'photo', None) is not None or
                getattr(message, 'document', None) is not None):
            raise TypeError('this Telegram media is not a reusable file')
        return await self._client.send_file(destination_chat, media, caption=caption)
