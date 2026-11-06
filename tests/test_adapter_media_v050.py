"""Adapters must preserve native Telegram upload representation."""
import asyncio
import sys
from types import ModuleType

from iqgram.telethon_adapter import TelethonBackend
from iqgram.transfer import UploadedHandle


def test_adapter_document_photo_voice_sticker_modes(monkeypatch):
    class File:
        def __init__(self,*args): self.args=args
    class Sticker:
        def __init__(self, alt, stickerset): self.alt=alt;self.stickerset=stickerset
    class StickerSetEmpty:
        pass
    class Animated:
        pass
    modules={name: ModuleType(name) for name in ('telethon','telethon.tl','telethon.tl.types')}
    types=modules['telethon.tl.types']
    types.InputFile=File
    types.InputFileBig=File
    types.DocumentAttributeSticker=Sticker
    types.InputStickerSetEmpty=StickerSetEmpty
    types.DocumentAttributeAnimated=Animated
    for name,module in modules.items(): monkeypatch.setitem(sys.modules,name,module)

    class Tg:
        def __init__(self): self.sent=[]
        async def send_file(self, chat, raw, **kwargs):
            self.sent.append((chat,raw,kwargs))
            return 'sent'

    async def run():
        tg=Tg(); b=TelethonBackend(tg)
        def handle(name,kind):return UploadedHandle(7,1,name,False,'a'*32,kind)
        await b.send_uploaded('me',handle('picture.jpg','photo'))
        await b.send_uploaded('me',handle('voice.ogg','voice'))
        await b.send_uploaded('me',handle('sticker.webp','sticker'))
        await b.send_uploaded('me',handle('clip.gif','animation'))
        assert tg.sent[0][2]['force_document'] is False
        assert tg.sent[1][2]['voice_note'] is True
        assert isinstance(tg.sent[2][2]['attributes'][0],Sticker)
        assert isinstance(tg.sent[3][2]['attributes'][0],Animated)
    asyncio.run(run())


def test_download_adapter_does_not_copy_memoryview_chunks():
    """Avoid one full-size copy for every media chunk from Telethon."""
    buffer = memoryview(b'x' * 1024)
    class Stream:
        def __aiter__(self): return self
        async def __anext__(self):
            if getattr(self,'done',False):raise StopAsyncIteration
            self.done=True
            return buffer
        async def close(self):pass
    class Tg:
        def iter_download(self,*args,**kwargs):return Stream()
    async def run():
        backend=TelethonBackend(Tg())
        chunks=[part async for part in backend.iter_range('m',0,1,1024)]
        assert chunks[0] is buffer
    asyncio.run(run())
