"""Durable transfer queue. Running jobs are interrupted on restart to avoid duplicate uploads."""
from __future__ import annotations
import asyncio
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
from .transfer import timed_download, timed_upload, format_rate

logger = logging.getLogger(__name__)


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class JobStore:
    def __init__(self, location: Path):
        location = Path(location)
        location.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(location))
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('''CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL, chat_id TEXT NOT NULL,
            message_id INTEGER NOT NULL, owner_id INTEGER NOT NULL,
            status TEXT NOT NULL, stage TEXT NOT NULL DEFAULT 'queued',
            bytes_done INTEGER NOT NULL DEFAULT 0, bytes_total INTEGER NOT NULL DEFAULT 0,
            path TEXT NOT NULL DEFAULT '', result TEXT NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )''')
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def enqueue(self, kind: str, chat_id: int | str, message_id: int, owner_id: int) -> int:
        if kind not in ('download', 'mirror', 'benchmark'):
            raise ValueError('Unsupported queue job')
        if int(message_id) <= 0 or int(owner_id) <= 0:
            raise ValueError('message_id and owner_id must be positive')
        now = timestamp()
        cur = self.db.execute('''INSERT INTO jobs(kind,chat_id,message_id,owner_id,status,created_at,updated_at)
                                VALUES(?,?,?,?,?,?,?)''',
                              (kind,str(chat_id),message_id,owner_id,'queued',now,now))
        self.db.commit()
        return int(cur.lastrowid)

    def get(self, jid: int) -> dict | None:
        row = self.db.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
        return dict(row) if row else None

    def list_jobs(self, owner_id: int, limit: int = 10) -> list[dict]:
        return [dict(r) for r in self.db.execute('''SELECT * FROM jobs WHERE owner_id=?
                           ORDER BY id DESC LIMIT ?''',(owner_id,limit)).fetchall()]

    def pending_ids(self) -> list[int]:
        return [int(row[0]) for row in self.db.execute("SELECT id FROM jobs WHERE status='queued' ORDER BY id")]

    def set_status(self, jid: int, status: str, *, stage: str | None = None, error: str = '',
                   result: str = '', path: str | None = None) -> None:
        row = self.get(jid)
        if row is None:
            raise KeyError(jid)
        self.db.execute('''UPDATE jobs SET status=?,stage=?,error=?,result=?,path=?,updated_at=? WHERE id=?''',
                        (status, stage if stage is not None else row['stage'], error, result,
                         path if path is not None else row['path'], timestamp(), jid))
        self.db.commit()

    def update_progress(self, jid: int, current: int, total: int, stage: str) -> None:
        self.db.execute('''UPDATE jobs SET bytes_done=?,bytes_total=?,stage=?,updated_at=?
                           WHERE id=? AND status='running' ''',
                        (max(0,current),max(0,total),stage,timestamp(),jid))
        self.db.commit()

    def cancel(self, jid: int, owner_id: int) -> bool:
        cur = self.db.execute('''UPDATE jobs SET status='cancelled',stage='cancelled',updated_at=?
                WHERE id=? AND owner_id=? AND status IN ('queued','running')''',(timestamp(),jid,owner_id))
        self.db.commit()
        return cur.rowcount > 0

    def retry(self, jid: int, owner_id: int) -> bool:
        cur = self.db.execute('''UPDATE jobs SET status='queued',stage='queued',bytes_done=0,
                      bytes_total=0,error='',result='',updated_at=?
                      WHERE id=? AND owner_id=? AND status IN ('failed','interrupted')''',
                              (timestamp(),jid,owner_id))
        self.db.commit()
        return cur.rowcount > 0

    def recover(self) -> None:
        # Intentionally DON'T replay jobs that might have sent media before a crash.
        self.db.execute('''UPDATE jobs SET status='interrupted',stage='interrupted',
                     error='Process interrupted; use /retry to start from beginning',updated_at=?
                     WHERE status='running' ''',(timestamp(),))
        self.db.commit()


class TransferQueue:
    def __init__(self, client: Any, store: JobStore, download_root: Path, workers: int = 2,
                 on_finish=None, delete_after_mirror: bool = False):
        self.client = client
        self.store = store
        self.root = Path(download_root).resolve()
        self.workers = max(1, min(8, workers))
        self.on_finish = on_finish
        self.delete_after_mirror = delete_after_mirror
        self.jobs: asyncio.Queue[int] = asyncio.Queue()
        self.tasks: list[asyncio.Task] = []
        self._waiters: dict[int, asyncio.Event] = {}

    async def start(self) -> None:
        if self.tasks:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        self.store.recover()
        for jid in self.store.pending_ids():
            self.jobs.put_nowait(jid)
        self.tasks = [asyncio.create_task(self._worker(),name=f'iqgram-worker-{i}') for i in range(self.workers)]

    async def stop(self) -> None:
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        self.store.recover()

    async def enqueue(self, kind: str, chat_id: int | str, message_id: int, owner_id: int) -> int:
        jid = self.store.enqueue(kind, chat_id, message_id, owner_id)
        self.jobs.put_nowait(jid)
        return jid

    async def retry(self, jid: int, owner_id: int) -> bool:
        if not self.store.retry(jid, owner_id):
            return False
        self.jobs.put_nowait(jid)
        return True

    async def wait(self, jid: int) -> dict:
        # wait also works if the worker completed before registration
        event = self._waiters.setdefault(jid, asyncio.Event())
        row = self.store.get(jid)
        if row and row['status'] not in ('queued', 'running'):
            event.set()
        await event.wait()
        return self.store.get(jid)

    async def _worker(self) -> None:
        while True:
            jid = await self.jobs.get()
            try:
                job = self.store.get(jid)
                if job is None or job['status'] != 'queued':
                    continue
                await self._run_job(job)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception('Unexpected IQGram queue worker failure')
            finally:
                self.jobs.task_done()
                event = self._waiters.get(jid)
                if event:
                    event.set()

    async def _run_job(self, job: dict) -> None:
        jid=job['id']
        self.store.set_status(jid,'running',stage='downloading')
        async def progress(current: int, total: int, stage: str):
            if self.store.get(jid)['status'] == 'cancelled':
                self.client.stop_transmission()  # Must be invoked inside the progress callback.
            self.store.update_progress(jid,current,total,stage)

        async def downloading(current, total):
            await progress(current, total, 'downloading')

        async def uploading(current, total):
            await progress(current,total,'uploading')

        try:
            dest = self.root / f'job_{jid:08d}'
            path, dl = await timed_download(self.client, self._chat(job['chat_id']), job['message_id'], dest, downloading)
            if self.store.get(jid)['status'] == 'cancelled':
                return
            if job['kind'] == 'download':
                result = f'Downloaded {path.name} at {format_rate(dl.rate)}'
                self.store.set_status(jid,'completed',stage='complete',result=result,path=str(path))
            else:
                self.store.set_status(jid,'running',stage='uploading',path=str(path))
                sent, ul = await timed_upload(self.client, self._chat(job['chat_id']), path, '', uploading)
                if self.store.get(jid)['status'] == 'cancelled':
                    return
                result = f'Download {format_rate(dl.rate)} | Upload {format_rate(ul.rate)} | Message #{sent.id}'
                self.store.set_status(jid,'completed',stage='complete',result=result,path=str(path))
                if self.delete_after_mirror:
                    try:
                        path.unlink(missing_ok=True)
                        dest.rmdir()
                    except OSError:
                        logger.warning('Job #%s uploaded; optional local cleanup was incomplete', jid)
        except asyncio.CancelledError:
            # A hard shutdown must never mark an in-progress upload completed.
            if self.store.get(jid)['status'] == 'running':
                self.store.set_status(jid,'interrupted',stage='interrupted',error='Worker interrupted during shutdown')
            raise
        except Exception as exc:
            if self.store.get(jid)['status'] != 'cancelled':
                self.store.set_status(jid,'failed',stage='failed',error=f'{type(exc).__name__}: {str(exc)[:350]}')
        finally:
            if self.on_finish:
                try:
                    await self.on_finish(self.store.get(jid))
                except Exception:
                    logger.exception('Could not deliver job completion message')

    @staticmethod
    def _chat(value: str) -> int | str:
        return int(value) if value.lstrip('-').isdigit() else value
