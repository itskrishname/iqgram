"""Optional example: Pyrogram/Pyrofork bot + separate IQGram MTProto session.

Requires `pip install pyrogram` (or compatible Pyrofork); IQGram itself
remains independent of either framework. Credentials are loaded from env.

NOTE: A separate IQGram session does not automatically inherit the
Pyrogram/Pyrofork client peer cache or message access. Use an IQGram-
authorized Telegram source chat; not every private chat ID is resolvable.
"""
import asyncio
import os
import tempfile
from pathlib import Path

from pyrogram import Client as PyrogramClient, filters, idle
from iqgram import Client as IQClient, TransferOptions


async def main() -> None:
    api_id = int(os.environ['IQGRAM_API_ID'])
    api_hash = os.environ['IQGRAM_API_HASH']
    token = os.environ['IQGRAM_BOT_TOKEN']
    admin_id = int(os.environ['IQGRAM_ALLOWED_USER_ID'])
    source_chat = os.environ['IQGRAM_SOURCE_CHAT']  # e.g. @channel_you_control
    source_message = int(os.environ['IQGRAM_SOURCE_MESSAGE_ID'])

    # Separate session filenames; do NOT point two libraries at the same .session.
    pyrogram_bot = PyrogramClient(
        'example_pyrogram', api_id, api_hash, bot_token=token,
        workers=8, max_concurrent_transmissions=16,
    )
    iq = IQClient(
        'example_iqgram_companion', api_id, api_hash,
        bot_token=token, options=TransferOptions(download_workers=8, upload_workers=8),
    )

    @pyrogram_bot.on_message(filters.command('iqtest') & filters.private)
    async def on_iqtest(_bot, message):
        if not message.from_user or message.from_user.id != admin_id:
            return
        try:
            with tempfile.TemporaryDirectory(prefix='iqgram-demo-') as folder:
                dest = Path(folder) / 'sample.bin'
                result = await iq.download(source_chat, source_message, dest)
                await message.reply_text(
                    f'IQGram downloaded {result.bytes_transferred} bytes '
                    f'at {result.bytes_per_second / 1048576:.2f} MiB/s'
                )
        except Exception as exc:
            print('IQGram transfer error:', type(exc).__name__, str(exc))
            await message.reply_text('Transfer failed; check private logs and source chat access.')

    await iq.start()
    try:
        await pyrogram_bot.start()
        await idle()
    finally:
        await pyrogram_bot.stop()
        await iq.close()


if __name__ == '__main__':
    asyncio.run(main())
