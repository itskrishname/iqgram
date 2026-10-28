"""Controlled bot commands for the IQGram transfer queue.

    All commands require an explicit ALLOWED_USER_IDS allowlist.
"""
from __future__ import annotations
import logging
from pathlib import Path
from .client import Client
from .settings import Settings
from .queue import JobStore, TransferQueue
from .paths import safe_upload_source
from .progress import size_text
from .transfer import timed_upload, format_rate

log=logging.getLogger(__name__)


def allowed(user_id: int | None, settings: Settings) -> bool:
    return user_id is not None and user_id in settings.allowed_ids


def get_arg(text: str, name: str) -> int:
    parts=(text or '').split()
    if len(parts)!=2 or not parts[1].isdigit() or int(parts[1])<1:
        raise ValueError(f'Usage: /{name} <positive_job_id>')
    return int(parts[1])


async def serve(settings: Settings):
    """Connect MTProto bot and run until interrupted."""
    settings.validate('bot')
    if not settings.allowed_ids:
        raise ValueError('Set ALLOWED_USER_IDS before starting bot mode (secure-by-default)')
    from wzgram import filters, idle

    workdir=settings.workdir
    store=JobStore(workdir/'jobs.sqlite3')
    wrapped=Client('bot',settings,updates=True)
    app=wrapped.raw

    async def finished(job: dict):
        try:
            status=job['status'].upper()
            detail=job['result'] or job['error'] or job['path']
            if detail:
                detail=detail[:500]
            await app.send_message(job['chat_id'] if not str(job['chat_id']).lstrip('-').isdigit() else int(job['chat_id']),
                                   f'IQGram job #{job["id"]}: {status}\n{detail}')
        except Exception:
            log.exception('Could not send completion notification')

    queue=TransferQueue(app,store,workdir/'downloads',settings.queue_workers,finished,
                        delete_after_mirror=settings.delete_after_mirror)

    async def gate(message):
        uid=getattr(getattr(message,'from_user',None),'id',None)
        if not allowed(uid,settings):
            await message.reply_text('Access denied. Your Telegram user ID must be in ALLOWED_USER_IDS.')
            return None
        return uid

    @app.on_message(filters.command(['start','help']))
    async def start_handler(client,message):
        if await gate(message) is None:
            return
        await message.reply_text(
            'IQGram transfer bot\n\n'
            'Reply to a media message with /download to save it on VPS.\n'
            'Reply with /mirror to download and send it back as a document.\n'
            'Reply with /benchmark for download+upload speeds.\n'
            'Use /status, /cancel <id>, /retry <id>.\n'
            'Use /upload <job_id> to send back a completed download.\n'
            'Only approved users can use these commands.')

    @app.on_message(filters.command(['download','mirror','benchmark']))
    async def enqueue_handler(client,message):
        uid=await gate(message)
        if uid is None:
            return
        reply=getattr(message,'reply_to_message',None)
        if not reply or not any(getattr(reply,k,None) for k in ('document','video','photo','audio','voice','sticker','animation','video_note')):
            await message.reply_text('Reply to a downloadable media message with this command.')
            return
        kind=(message.text or '').split()[0].split('@')[0].lstrip('/').lower()
        jid=await queue.enqueue(kind,message.chat.id,reply.id,uid)
        await message.reply_text(f'IQGram job #{jid} queued. Check /status or /cancel {jid}.')

    @app.on_message(filters.command('status'))
    async def status_handler(client,message):
        uid=await gate(message)
        if uid is None:
            return
        entries=store.list_jobs(uid,limit=10)
        if not entries:
            await message.reply_text('No IQGram jobs yet.')
            return
        parts=[]
        for job in entries:
            percent = (100*job['bytes_done']/job['bytes_total']) if job['bytes_total'] else 0
            size = f'{size_text(job["bytes_done"])} / {size_text(job["bytes_total"])}'
            parts.append(f'#{job["id"]} {job["kind"]} | {job["status"]} | {job["stage"]} | {percent:.1f}% ({size})')
        await message.reply_text('IQGram jobs:\n'+'\n'.join(parts))

    @app.on_message(filters.command('cancel'))
    async def cancel_handler(client,message):
        uid=await gate(message)
        if uid is None:
            return
        try:
            jid=get_arg(message.text,'cancel')
        except ValueError as exc:
            await message.reply_text(str(exc))
            return
        ok=store.cancel(jid,uid)
        await message.reply_text(f'Job #{jid}: cancellation requested.' if ok else 'Job not found, finished or not yours.')

    @app.on_message(filters.command('retry'))
    async def retry_handler(client,message):
        uid=await gate(message)
        if uid is None:
            return
        try:
            jid=get_arg(message.text,'retry')
        except ValueError as exc:
            await message.reply_text(str(exc))
            return
        ok=await queue.retry(jid,uid)
        await message.reply_text(f'Job #{jid}: queued for a fresh transfer.' if ok else 'Only failed/interrupted jobs you own can be retried.')

    @app.on_message(filters.command('upload'))
    async def upload_handler(client,message):
        uid=await gate(message)
        if uid is None:
            return
        try:
            jid=get_arg(message.text,'upload')
            job=store.get(jid)
            if job is None or job['owner_id']!=uid or job['status']!='completed' or not job['path']:
                raise ValueError('A completed download job you own is required')
            # Allow only completed local downloads, never arbitrary VPS paths.
            path=safe_upload_source(workdir/'downloads',str(Path(job['path']).resolve().relative_to((workdir/'downloads').resolve())))
            sent,measure=await timed_upload(client,message.chat.id,path)
            await message.reply_text(f'Uploaded as message #{sent.id} at {format_rate(measure.rate)}')
        except (ValueError,FileNotFoundError) as exc:
            await message.reply_text(f'Cannot upload: {exc}')

    try:
        await app.start()
        await queue.start()
        log.info('IQGram started with %d worker(s) and %d authorized IDs', settings.queue_workers,len(settings.allowed_ids))
        await idle()
    finally:
        await queue.stop()
        store.close()
        if getattr(app,'is_initialized',False):
            await app.stop()
