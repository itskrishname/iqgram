"""Public integration API: wrapping a running Telethon bot must not own its session."""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import pytest

from iqgram import Client, TransferOptions


class ExistingTelegramBot:
    def __init__(self):
        self.alive = True
        self.starts = 0
        self.disconnects = 0
        self.data = b'Bot transfer works' * 2000

    def is_connected(self):
        return self.alive

    async def start(self, **kwargs):
        self.starts += 1

    async def disconnect(self):
        self.disconnects += 1
        self.alive = False

    async def get_messages(self, chat, ids):
        return SimpleNamespace(media='media-id', file=SimpleNamespace(size=len(self.data)))

    def iter_download(self, media, *, offset, limit, request_size, chunk_size):
        async def chunks():
            for index in range(limit):
                begin = offset + index * chunk_size
                block = self.data[begin:begin + chunk_size]
                if block:
                    yield block
        return chunks()

    async def send_file(self, *args, **kwargs):
        return SimpleNamespace(id=222)


async def _exercise_existing_bot():
    bot = ExistingTelegramBot()
    iq = Client.from_telethon(bot, options=TransferOptions(download_workers=4, upload_workers=4))
    assert iq.raw is bot
    assert iq._engine.options.download_workers == 4
    with TemporaryDirectory() as d:
        async with iq:
            result = await iq.download('source-chat', 100, Path(d) / 'media.bin')
            assert result.value.read_bytes() == bot.data
        assert bot.disconnects == 0
        assert bot.starts == 0
    assert (await iq.start()) is iq
    await iq.close()
    assert bot.disconnects == 0
    bot.alive = False
    with pytest.raises(RuntimeError, match='already connected'):
        await iq.start()


def test_existing_telethon_bot_can_reuse_its_session_without_client_ownership():
    asyncio.run(_exercise_existing_bot())


def test_bot_transfer_client_requires_existing_telegram_client():
    with pytest.raises(TypeError, match='Telethon'):
        Client.from_telethon(None)


def test_from_telethon_rejects_pyrogram_like_client_without_telethon_methods():
    class PyrogramLike:
        async def get_messages(self, *args):
            pass
    with pytest.raises(TypeError, match='Telethon'):
        Client.from_telethon(PyrogramLike())


def test_new_bot_token_client_still_owns_its_session():
    bot = ExistingTelegramBot()
    client = Client('test_bot_session', 123, 'test_hash', bot_token='test_bot_token', _telegram=bot)

    async def run():
        async with client:
            pass
    asyncio.run(run())
    assert bot.starts == 1
    assert bot.disconnects == 1
