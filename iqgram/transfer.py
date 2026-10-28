"""One-file transfer operations through the documented WZGram MTProto API."""
from __future__ import annotations
from pathlib import Path
from time import monotonic
from dataclasses import dataclass
from typing import Any, Callable
import inspect

ProgressCallback = Callable[[int, int], Any]


def has_media(message: Any) -> bool:
    return bool(message and any(getattr(message, field, None) for field in (
        'document','video','photo','audio','voice','animation','sticker','video_note'
    )))


def format_rate(bytes_per_second: float) -> str:
    return f'{bytes_per_second / (1024 * 1024):.2f} MiB/s'


@dataclass
class TransferMeasurement:
    bytes_total: int = 0
    seconds: float = 0.0
    @property
    def rate(self) -> float:
        return self.bytes_total / max(self.seconds, 0.0001)


async def download_message(client: Any, chat_id: int | str, message_id: int,
                           destination: Path, progress: ProgressCallback | None = None) -> Path:
    if message_id <= 0:
        raise ValueError('message_id must be positive')
    message = await client.get_messages(chat_id, message_id, replies=0)
    if not has_media(message):
        raise ValueError('Message has no downloadable media, or is not accessible')
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    # The trailing slash ensures the library treats this as a directory.
    async def progress_callback(current: int, total: int):
        if progress:
            result = progress(current, total)
            if inspect.isawaitable(result):
                await result
    output = await client.download_media(message, file_name=str(destination) + '/', progress=progress_callback if progress else None)
    if not output:
        raise RuntimeError('Telegram download was cancelled or failed')
    path = Path(output).resolve()
    if not path.is_file() or not path.is_relative_to(destination.resolve()):
        raise RuntimeError('Downloader returned a missing or unsafe file path')
    return path


async def upload_file(client: Any, chat_id: int | str, path: Path, caption: str = '',
                      progress: ProgressCallback | None = None) -> Any:
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    async def progress_callback(current: int, total: int):
        if progress:
            result = progress(current, total)
            if inspect.isawaitable(result):
                await result
    sent = await client.send_document(chat_id, document=str(path), caption=caption or None,
                                      progress=progress_callback if progress else None)
    if sent is None:
        raise RuntimeError('Telegram upload was cancelled or failed')
    return sent


async def timed_download(client: Any, chat_id: int | str, message_id: int,
                         destination: Path, progress: ProgressCallback | None = None) -> tuple[Path, TransferMeasurement]:
    start = monotonic()
    path = await download_message(client, chat_id, message_id, destination, progress=progress)
    return path, TransferMeasurement(path.stat().st_size, monotonic() - start)


async def timed_upload(client: Any, chat_id: int | str, path: Path, caption: str = '',
                       progress: ProgressCallback | None = None) -> tuple[Any, TransferMeasurement]:
    start = monotonic()
    message = await upload_file(client, chat_id, path, caption, progress=progress)
    return message, TransferMeasurement(path.stat().st_size, monotonic() - start)
