"""Run an existing Telethon bot using IQGram for media transfers.

Install: pip install -e '.[fast]'   (Telethon is included by IQGram)
Set IQGRAM_API_ID, IQGRAM_API_HASH, IQGRAM_BOT_TOKEN and IQGRAM_ALLOWED_USER_ID.
This is an optional example, not a bot application bundled with the library.
"""
import asyncio
import os
import tempfile
from pathlib import Path

from telethon import TelegramClient, events
from iqgram import Client as IQClient, TransferOptions


def safe_filename(name: str | None, *, photo: bool = False) -> str:
    """Never use an untrusted Telegram filename as a filesystem path."""
    candidate = (name or ('photo.jpg' if photo else 'media.bin')).replace('\\', '/').split('/')[-1]
    if not candidate or candidate in ('.', '..'):
        return 'media.bin'
    return candidate[:150]


async def main() -> None:
    api_id = int(os.environ['IQGRAM_API_ID'])
    api_hash = os.environ['IQGRAM_API_HASH']
    token = os.environ['IQGRAM_BOT_TOKEN']
    allowed_user_id = int(os.environ['IQGRAM_ALLOWED_USER_ID'])

    bot = TelegramClient('example_existing_bot', api_id, api_hash)
    await bot.start(bot_token=token)
    iq = IQClient.from_telethon(
        bot, options=TransferOptions(download_workers=4, upload_workers=4)
    )

    @bot.on(events.NewMessage(pattern=r'^/iqcopy(?:@\w+)?$'))
    async def on_copy(event) -> None:
        if event.sender_id != allowed_user_id:
            return
        original = await event.get_reply_message()
        if original is None or original.media is None or original.file is None:
            await event.reply('Reply to a file/photo first.')
            return
        try:
            with tempfile.TemporaryDirectory(prefix='iqgram-demo-') as folder:
                filename = safe_filename(original.file.name, photo=bool(original.photo))
                target = Path(folder) / filename
                await iq.download(event.chat_id, original.id, target)
                uploaded = await iq.upload(target, event.chat_id, media_kind='document')
                await event.reply(f'IQGram sent message {uploaded.value.id}.')
        except Exception as exc:
            # Keep sensitive RPC details out of public bot replies.
            print('IQGram transfer error:', type(exc).__name__, str(exc))
            await event.reply('Transfer failed; see private server logs.')

    try:
        await bot.run_until_disconnected()
    finally:
        # IQGram does not disconnect the externally owned Telethon session.
        await iq.close()
        await bot.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
