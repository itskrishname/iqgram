import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import pytest

from iqgram import Client, TransferOptions

class TelegramFake:
    def __init__(self, source=b'source media'):
        self.source = source
        self.started = []
        self.disconnected = False
    async def start(self, **kw): self.started.append(kw)
    async def disconnect(self): self.disconnected = True
    async def get_messages(self, chat, ids):
        return SimpleNamespace(media='media', file=SimpleNamespace(size=len(self.source)), id=ids)

class TransportFake:
    def __init__(self, telegram): self.telegram=telegram;self.calls=[]
    async def iter_range(self, media, offset, chunk_count, chunk_size):
        self.calls.append(('read',media,offset))
        for i in range(chunk_count):
            yield self.telegram.source[offset+i*chunk_size:offset+(i+1)*chunk_size]
    async def save_part(self, file_id, part, total_parts, data, is_big):
        self.calls.append(('write', part, data))
        return True
    async def send_uploaded(self, chat, handle, caption=None):
        self.calls.append(('send',chat, handle, caption))
        return SimpleNamespace(id=15)

def test_user_and_bot_start_without_config_file():
    async def run():
        bot = TelegramFake()
        client = Client('bot_session', api_id=123, api_hash='hash', bot_token='token', _telegram=bot, _backend=TransportFake(bot))
        await client.start()
        assert bot.started == [{'bot_token':'token'}]
        await client.close()
        assert bot.disconnected
        user=TelegramFake()
        client=Client('user_session',123,'hash',_telegram=user,_backend=TransportFake(user))
        async with client:
            assert user.started == [{}]
        assert user.disconnected
    asyncio.run(run())

def test_client_download_and_upload_use_transfer_engine():
    async def run():
        tg=TelegramFake(b'hello world'*20000)
        backend=TransportFake(tg)
        client=Client('session',1,'h',_telegram=tg,_backend=backend,options=TransferOptions(download_workers=2))
        with TemporaryDirectory() as d:
            async with client:
                result=await client.download('me',24,Path(d)/'out.bin')
                assert result.value.read_bytes() == tg.source
                uploaded=await client.upload(Path(d)/'out.bin','me',caption='hi')
                assert uploaded.value.id == 15
                assert any(c[0]=='send' and c[3]=='hi' for c in backend.calls)
    asyncio.run(run())

def test_client_rejects_missing_media():
    async def run():
        tg=TelegramFake()
        async def no_message(chat, ids): return None
        tg.get_messages=no_message
        client=Client('session',1,'h',_telegram=tg,_backend=TransportFake(tg))
        with pytest.raises(ValueError,match='no media'):
            await client.download('me',100,'out.bin')
    asyncio.run(run())

def test_client_requires_positive_api_id():
    with pytest.raises(ValueError):
        Client('user',0,'hash')
