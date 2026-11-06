"""MTProto adapter. Telethon handles authorization, RPC and datacenter routing.

IQGram implements the chunk scheduling above this adapter, rather than
relying on Telethon's download_media/upload_file scheduling.
"""
from __future__ import annotations
from typing import Any, AsyncIterator
from .transfer import UploadedHandle

class TelethonBackend:
    def __init__(self, telegram: Any):
        self.telegram = telegram

    async def iter_range(self, media: Any, offset: int, chunk_count: int, chunk_size: int) -> AsyncIterator[bytes]:
        stream = self.telegram.iter_download(
            media,
            offset=offset,
            limit=chunk_count,
            request_size=chunk_size,
            chunk_size=chunk_size,
        )
        try:
            async for data in stream:
                # Telethon sometimes yields memoryview; pwrite accepts buffer
                # objects, so don't create an unnecessary 512KiB/1MiB copy.
                yield data if isinstance(data, (bytes, memoryview)) else bytes(data)
        finally:
            # Telethon iterator supports close(). The best-effort cleanup
            # helps release borrowed DC senders after cancellation/failure.
            close = getattr(stream, 'close', None)
            if close is not None:
                await close()

    async def save_part(self, file_id: int, part: int, total_parts: int, data: bytes, is_big: bool) -> bool:
        from telethon.tl.functions.upload import SaveBigFilePartRequest, SaveFilePartRequest
        if is_big:
            result = await self.telegram(SaveBigFilePartRequest(file_id, part, total_parts, data))
        else:
            result = await self.telegram(SaveFilePartRequest(file_id, part, data))
        return bool(result)

    async def send_uploaded(self, chat: Any, handle: UploadedHandle, caption: str | None = None) -> Any:
        from telethon.tl.types import InputFile, InputFileBig
        if handle.big:
            raw = InputFileBig(handle.file_id, handle.parts, handle.name)
        else:
            raw = InputFile(handle.file_id, handle.parts, handle.name, handle.md5_checksum)
        from .media import send_options
        kwargs = send_options(handle)
        # Telegram's native animated/sticker types require explicit attributes.
        if handle.media_kind == 'animation':
            from telethon.tl.types import DocumentAttributeAnimated
            kwargs['attributes'] = [DocumentAttributeAnimated()]
        elif handle.media_kind == 'sticker':
            from telethon.tl.types import DocumentAttributeSticker, InputStickerSetEmpty
            kwargs['attributes'] = [DocumentAttributeSticker(alt='', stickerset=InputStickerSetEmpty())]
        return await self.telegram.send_file(chat, raw, caption=caption, **kwargs)
