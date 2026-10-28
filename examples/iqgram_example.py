"""After filling config.py, send a known Saved Messages media back to yourself."""
import asyncio
from iqgram import Client


async def main():
    async with Client('user') as iq:
        path=await iq.download('me',123,'./downloads')  # replace 123
        sent=await iq.upload('me',path)
        print('Sent:',sent.id)


if __name__=='__main__':
    asyncio.run(main())
