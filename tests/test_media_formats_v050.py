import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import pytest

from iqgram.media import send_options
from iqgram.transfer import UploadedHandle, TransferEngine, TransferOptions
from iqgram.client import Client


@pytest.mark.parametrize('kind,name,expected', [
    ('document','hello.mp4', {'force_document': True}),
    ('auto','file.bin', {'force_document': True}),
    ('auto','pic.jpg', {'force_document': False}),
    ('auto','movie.mp4', {'force_document': False, 'supports_streaming': True}),
    ('photo','anything.jpeg', {'force_document': False}),
    ('video','movie.mp4', {'force_document': False, 'supports_streaming': True}),
    ('video','movie.mkv', {'force_document': False}),
    ('document','my-archive.7z', {'force_document': True}),
    ('audio','song.mp3', {'force_document': False}),
    ('voice','note.ogg', {'force_document': False, 'voice_note': True}),
    ('video_note','round.mp4', {'force_document': False, 'video_note': True}),
    ('animation','dance.gif', {'force_document': False}),
    ('sticker','sticker.webp', {'force_document': False}),
])
def test_native_media_kind_options(kind, name, expected):
    opt = send_options(UploadedHandle(1,1,name,False,'f'*32,media_kind=kind))
    for k, v in expected.items():
        assert opt[k] == v


def test_unknown_media_kind_rejected():
    with pytest.raises(ValueError, match='media_kind'):
        send_options(UploadedHandle(1,1,'x.txt',False,'f'*32,media_kind='poll'))


def test_known_file_as_photo_must_be_compatible_extension():
    with pytest.raises(ValueError, match='photo'):
        send_options(UploadedHandle(1,1,'not-photo.zip',False,'f'*32,media_kind='photo'))


def test_engine_upload_preserves_kind_without_changing_file_bytes():
    class Fake:
        def __init__(self): self.content={}; self.handle=None
        async def save_part(self, file_id, part, total_parts, data, is_big):
            self.content[part] = data
            return True
        async def send_uploaded(self, chat, handle, caption=None):
            self.handle=handle
            return SimpleNamespace(id=11)
    async def run():
        b=Fake()
        with TemporaryDirectory() as td:
            p=Path(td)/'audio.ogg'
            p.write_bytes(b'A' * 10000)
            res = await TransferEngine(b,TransferOptions(upload_workers=4)).upload(p,'me',media_kind='voice')
            assert b.handle.media_kind == 'voice'
            assert b''.join(b.content[i] for i in sorted(b.content)) == p.read_bytes()
            assert res.value.id == 11
    asyncio.run(run())


def test_download_profile_has_four_measured_workers_and_total_bytes():
    class Fake:
        async def iter_range(self, media, offset, chunk_count, chunk_size):
            for i in range(chunk_count):
                await asyncio.sleep(0)
                yield data[offset+i*chunk_size:offset+(i+1)*chunk_size]
    async def run():
        nonlocal data
        data = b'x' * (524288*4+10)
        with TemporaryDirectory() as td:
            result=await TransferEngine(Fake(),TransferOptions(download_workers=4)).download('m',len(data),Path(td)/'a',profile=True)
            assert result.profile is not None
            assert len(result.profile.workers) == 4
            assert sum(w.transferred for w in result.profile.workers) == len(data)
            assert all(w.read_wait_seconds >= 0 for w in result.profile.workers)
            result2=await TransferEngine(Fake(),TransferOptions(download_workers=4)).download('m',len(data),Path(td)/'b')
            assert result2.profile is None
    data=b''
    asyncio.run(run())


def test_client_downloads_unknown_size_photo_atomically():
    class Telegram:
        async def get_messages(self, chat, ids):
            return SimpleNamespace(media='photo',photo=object(),document=None,file=SimpleNamespace(size=None))
        async def download_media(self, message, file=None, **kwargs):
            Path(file).write_bytes(b'PHOTO_BYTES')
            return str(file)
    async def run():
        with TemporaryDirectory() as td:
            tg=Telegram()
            client=Client('test',1,'hash',_telegram=tg,_backend=object())
            path=Path(td)/'pic.jpg'
            result=await client.download('me',1,path)
            assert path.read_bytes() == b'PHOTO_BYTES'
            assert result.bytes_transferred == 11
            assert list(Path(td).iterdir()) == [path]
            with pytest.raises(FileExistsError):
                await client.download('me',1,path)
    asyncio.run(run())


def test_non_file_media_is_reported_as_unsupported_not_empty():
    class Telegram:
        async def get_messages(self, chat, ids):
            return SimpleNamespace(media='poll',photo=None,document=None,file=None)
    async def run():
        client=Client('test',1,'hash',_telegram=Telegram(),_backend=object())
        with TemporaryDirectory() as td:
            with pytest.raises((TypeError,ValueError),match='file|media'):
                await client.download('me',2,Path(td)/'x')
    asyncio.run(run())


def test_client_can_reuse_unprotected_existing_media_without_download_upload():
    class Telegram:
        def __init__(self): self.calls=[]
        async def get_messages(self, chat, ids):
            return SimpleNamespace(media='existing_file',document=object(),photo=None,noforwards=False)
        async def send_file(self, chat, file, **kwargs):
            self.calls.append((chat,file,kwargs))
            return SimpleNamespace(id=44)
    async def run():
        tg=Telegram()
        client=Client('test',1,'hash',_telegram=tg,_backend=object())
        result=await client.reuse_media('source',13,'destination',caption='Shared')
        assert result.id == 44
        assert tg.calls == [('destination','existing_file',{'caption':'Shared'})]
    asyncio.run(run())


def test_client_rejects_protected_media_copy():
    class Telegram:
        async def get_messages(self, chat, ids):
            return SimpleNamespace(media='existing_file',document=object(),photo=None,noforwards=True)
    async def run():
        client=Client('test',1,'hash',_telegram=Telegram(),_backend=object())
        with pytest.raises(PermissionError,match='protected'):
            await client.reuse_media('source',13,'destination')
    asyncio.run(run())


def test_unknown_size_photo_callback_failure_leaves_no_output():
    class Telegram:
        async def get_messages(self, chat, ids):
            return SimpleNamespace(media='photo', photo=object(), document=None, file=SimpleNamespace(size=None))
        async def download_media(self, message, file=None):
            Path(file).write_bytes(b'valid photo')
            return str(file)
    def broken_callback(_):
        raise RuntimeError('progress callback failed')
    async def run():
        with TemporaryDirectory() as td:
            path=Path(td)/'pic.jpg'
            client=Client('test',1,'hash',_telegram=Telegram(),_backend=object())
            with pytest.raises(RuntimeError,match='progress callback failed'):
                await client.download('me',1,path,progress=broken_callback)
            assert list(Path(td).iterdir()) == []
    asyncio.run(run())
