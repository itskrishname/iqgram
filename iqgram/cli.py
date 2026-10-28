"""CLI for IQGram. Run `iqgram --help`."""
from __future__ import annotations
import argparse
import asyncio
import importlib.metadata
import json
import logging
from pathlib import Path
from .settings import load_settings
from .client import Client
from .progress import ProgressMeter
from .transfer import timed_download, timed_upload, format_rate


def parse_chat(value: str) -> int | str:
    return int(value) if value.lstrip('-').isdigit() else value


def print_progress(label: str):
    meter=ProgressMeter(label)
    async def update(current: int, total: int):
        text=meter.update(current,total)
        if text:
            print('\r'+text.ljust(95),end='\n' if current>=total else '',flush=True)
    return update


def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(prog='iqgram',description='IQGram Telegram MTProto upload/download and benchmark suite')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor',help='Check dependencies and configuration without connecting to Telegram')
    sub.add_parser('bot',help='Start allowlisted Telegram transfer bot')
    login=sub.add_parser('login',help='Connect and save a bot or interactive user session')
    login.add_argument('--account',choices=['bot','user'],default='user')
    for kind in ('download','upload','benchmark'):
        cmd=sub.add_parser(kind)
        cmd.add_argument('--account',choices=['bot','user'],default='user')
        cmd.add_argument('--chat',required=True,help='Source chat ID or username; user accounts can use me')
        if kind in ('download','benchmark'):
            cmd.add_argument('--message',required=True,type=int,help='Telegram source message ID')
            cmd.add_argument('--out',default=None,help='Download directory')
        if kind=='upload':
            cmd.add_argument('--file',required=True,help='Local file path to upload')
            cmd.add_argument('--caption',default='')
        if kind=='benchmark':
            cmd.add_argument('--upload-chat',default=None,help='Optional destination chat; omit for download-only benchmark')
    return p


async def _run(args, settings):
    if args.command=='bot':
        from .bot import serve
        await serve(settings)
        return
    async with Client(args.account,settings) as client:
        if args.command=='login':
            me=await client.get_me()
            print(f'Signed in: {me.id} ({getattr(me,"username",None) or getattr(me,"first_name", "account")})')
            return
        dest=Path(args.out or (settings.workdir/'downloads'/'cli')) if hasattr(args,'out') else None
        chat=parse_chat(args.chat)
        if args.command=='download':
            path,measurement=await timed_download(client.raw,chat,args.message,dest,print_progress('Downloading'))
            print(f'Downloaded: {path}\nSpeed: {format_rate(measurement.rate)} in {measurement.seconds:.2f} seconds')
        elif args.command=='upload':
            sent,measurement=await timed_upload(client.raw,chat,Path(args.file),args.caption,print_progress('Uploading'))
            print(f'Uploaded message #{sent.id}\nSpeed: {format_rate(measurement.rate)} in {measurement.seconds:.2f} seconds')
        elif args.command=='benchmark':
            result=await client.benchmark(chat,args.message,dest,
                                          parse_chat(args.upload_chat) if args.upload_chat else None,
                                          print_progress('Transfer'))
            print('\n'+json.dumps(result,indent=2))


def main(argv=None) -> int:
    args=parser().parse_args(argv)
    if args.command=='doctor':
        from . import __version__
        print(f'IQGram {__version__}')
        try:
            print(f'WZGram: {importlib.metadata.version("wzgram")}')
        except importlib.metadata.PackageNotFoundError:
            print('WZGram: MISSING (pip install -e .)')
        try:
            settings=load_settings()
            print(f'API ID present: {bool(settings.api_id)}')
            print(f'API Hash present: {bool(settings.api_hash)}')
            print(f'Bot Token present: {bool(settings.bot_token)}')
            print(f'Allowed users: {len(settings.allowed_ids)}')
            print(f'Data path: {settings.workdir}')
        except (ValueError, OSError) as exc:
            print(f'Invalid configuration: {exc}')
            return 1
        return 0
    try:
        settings=load_settings()
        settings.validate('bot' if args.command=='bot' else args.account)
        asyncio.run(_run(args, settings))
        return 0
    except (ValueError,RuntimeError,FileNotFoundError,PermissionError) as exc:
        print(f'IQGram error: {exc}')
        return 1
    except KeyboardInterrupt:
        print('IQGram stopped.')
        return 130


if __name__=='__main__':
    raise SystemExit(main())
