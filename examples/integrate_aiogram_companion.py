"""Optional example: Aiogram 3 bot commands with separate IQGram MTProto client.

Install Aiogram separately: pip install 'aiogram>=3,<4'
The IQGram connection has a distinct MTProto session; it is not the
Aiogram Bot API HTTP connection or Telegram file_id downloader.
"""
import asyncio
import os
import tempfile
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from iqgram import Client as IQClient, TransferOptions


async def main() -> None:
    api_id = int(os.environ['IQGRAM_API_ID'])
    api_hash = os.environ['IQGRAM_API_HASH']
    token = os.environ['IQGRAM_BOT_TOKEN']
    admin_id = int(os.environ['IQGRAM_ALLOWED_USER_ID'])
    source_chat = os.environ['IQGRAM_SOURCE_CHAT']
    source_message = int(os.environ['IQGRAM_SOURCE_MESSAGE_ID'])

    bot = Bot(token)
    dp = Dispatcher()
    iq = IQClient('example_iqgram_aiogram', api_id, api_hash, bot_token=token,
                  options=TransferOptions(download_workers=4, upload_workers=4))

    @dp.message(Command('iqtest'))
    async def on_iqtest(message: Message) -> None:
        if message.from_user is None or message.from_user.id != admin_id:
            return
        try:
            with tempfile.TemporaryDirectory(prefix='iqgram-demo-') as folder:
                output = Path(folder) / 'sample.bin'
                result = await iq.download(source_chat, source_message, output)
                await message.answer(
                    f'IQGram downloaded {result.bytes_transferred} bytes '
                    f'at {result.bytes_per_second / 1048576:.2f} MiB/s'
                )
        except Exception as exc:
            print('IQGram transfer error:', type(exc).__name__, str(exc))
            await message.answer('IQGram transfer failed; check private logs.')

    await iq.start()
    try:
        await dp.start_polling(bot)
    finally:
        await iq.close()
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())
