"""Example for developers. No config.py needed. Supply your credentials yourself."""
import asyncio
import os
from iqgram import Client, TransferOptions

async def main():
    async with Client(
        'my_session',
        api_id=int(os.environ['IQGRAM_API_ID']),
        api_hash=os.environ['IQGRAM_API_HASH'],
        bot_token=os.getenv('IQGRAM_BOT_TOKEN'),  # omit for user sessions
        options=TransferOptions(download_workers=4, upload_workers=4),
    ) as client:
        # Provide an authorized message ID and chat.
        result = await client.download('me', 123, './document.bin')
        print(f'Download: {result.bytes_per_second / 1048576:.2f} MiB/s')
        # `me` is for a user session; for bots pass an accessible chat ID.
        sent = await client.upload('./document.bin', 'me')
        print('New message ID:', sent.value.id)

if __name__ == '__main__':
    asyncio.run(main())
