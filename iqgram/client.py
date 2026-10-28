"""Public IQGram client facade; media transport is WZGram (MTProto)."""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any
from .settings import Settings, load_settings
from .transfer import download_message, upload_file, timed_download, timed_upload


class Client:
    """Creates an isolated Telegram bot or user MTProto session.

    The underlying, maintained MTProto implementation is WZGram. IQGram
    adds its own application-facing API, queue, workflows and benchmarks.
    """
    def __init__(self, account: str = 'bot', settings: Settings | None = None,
                 *, updates: bool = False, raw_client: Any = None):
        self.account = account
        self.settings = settings if settings is not None else load_settings()
        self.settings.validate(account)
        self._raw = raw_client
        self.updates = updates

    @property
    def raw(self) -> Any:
        if self._raw is None:
            try:
                from wzgram import Client as WzClient
            except ImportError as exc:
                raise RuntimeError('WZGram dependency missing; install with: pip install -e .') from exc
            session_dir = self.settings.workdir / 'sessions'
            session_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(session_dir, 0o700)
            opts = dict(api_id=int(self.settings.api_id), api_hash=self.settings.api_hash,
                        workdir=str(session_dir), no_updates=not self.updates,
                        max_concurrent_transmissions=int(self.settings.max_concurrent_transmissions))
            if self.account == 'bot':
                opts['bot_token'] = self.settings.bot_token
            self._raw = WzClient(f'iqgram_{self.account}', **opts)
        return self._raw

    async def __aenter__(self) -> 'Client':
        await self.raw.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.raw.stop()

    async def start(self) -> 'Client':
        await self.raw.start()
        return self

    async def stop(self) -> None:
        await self.raw.stop()

    async def get_me(self) -> Any:
        return await self.raw.get_me()

    async def download(self, chat_id: int | str, message_id: int, directory: str | Path,
                       progress=None) -> Path:
        return await download_message(self.raw, chat_id, message_id, Path(directory), progress)

    async def upload(self, chat_id: int | str, filename: str | Path, caption: str = '', progress=None) -> Any:
        return await upload_file(self.raw, chat_id, Path(filename), caption, progress)

    async def benchmark(self, chat_id: int | str, message_id: int, directory: Path,
                        upload_chat: int | str | None = None, progress=None) -> dict:
        path, dl = await timed_download(self.raw, chat_id, message_id, Path(directory), progress)
        result: dict = dict(path=str(path), download_mib_s=round(dl.rate/1024**2, 3),
                            download_seconds=round(dl.seconds,3), size_bytes=dl.bytes_total)
        if upload_chat is not None:
            sent, ul = await timed_upload(self.raw, upload_chat, path, progress=progress)
            result.update(upload_mib_s=round(ul.rate/1024**2,3),
                          upload_seconds=round(ul.seconds,3), sent_message_id=sent.id)
        return result
