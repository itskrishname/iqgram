"""IQGram's transport-independent concurrent file scheduler.

This module contains application-agnostic transfer logic. It intentionally
contains no Telegram credentials, bot handlers, or application configuration.
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import math
import os
import secrets
import time
from dataclasses import dataclass, replace
from pathlib import Path
from contextlib import aclosing
from typing import Any, AsyncIterator, Callable, Protocol

CHUNK_SIZE = 512 * 1024
BIG_FILE_THRESHOLD = 10 * 1024 * 1024

class TransferError(RuntimeError):
    """A transfer did not complete or failed integrity checks."""

@dataclass(frozen=True)
class TransferOptions:
    download_workers: int = 4
    upload_workers: int = 4
    download_request_size: int = CHUNK_SIZE
    upload_pipeline_depth: int = 1

    def __post_init__(self) -> None:
        if type(self.download_workers) is not int or not 1 <= self.download_workers <= 32:
            raise ValueError('download_workers must be between 1 and 32')
        if type(self.upload_workers) is not int or not 1 <= self.upload_workers <= 32:
            raise ValueError('upload_workers must be between 1 and 32')
        if type(self.upload_pipeline_depth) is not int or not 1 <= self.upload_pipeline_depth <= 4:
            raise ValueError('upload_pipeline_depth must be between 1 and 4')
        if type(self.download_request_size) is not int or self.download_request_size not in (CHUNK_SIZE, 2 * CHUNK_SIZE):
            raise ValueError('download_request_size must be 524288 or 1048576 bytes')

@dataclass(frozen=True)
class Progress:
    transferred: int
    total: int
    elapsed: float
    direction: str

    @property
    def bytes_per_second(self) -> float:
        return self.transferred / max(self.elapsed, 1e-9)

    @property
    def percent(self) -> float:
        return self.transferred / self.total * 100 if self.total else 100.0

@dataclass(frozen=True)
class TransferResult:
    bytes_transferred: int
    elapsed_seconds: float
    direction: str
    value: Any
    profile: DownloadProfile | None = None

    @property
    def bytes_per_second(self) -> float:
        return self.bytes_transferred / max(self.elapsed_seconds, 1e-9)

@dataclass(frozen=True)
class WorkerProfile:
    worker_index: int
    transferred: int
    chunks: int
    read_wait_seconds: float
    disk_write_seconds: float


@dataclass(frozen=True)
class DownloadProfile:
    workers: tuple[WorkerProfile, ...]

    @property
    def total_read_wait_seconds(self) -> float:
        # Overlapping worker wait times: not elapsed wall time.
        return sum(w.read_wait_seconds for w in self.workers)

    @property
    def total_disk_write_seconds(self) -> float:
        return sum(w.disk_write_seconds for w in self.workers)


@dataclass(frozen=True)
class UploadedHandle:
    file_id: int
    parts: int
    name: str
    big: bool
    md5_checksum: str | None = None
    media_kind: str = "document"

class TransferBackend(Protocol):
    def iter_range(self, media: Any, offset: int, chunk_count: int, chunk_size: int) -> AsyncIterator[bytes]: ...
    async def save_part(self, file_id: int, part: int, total_parts: int, data: bytes, is_big: bool) -> bool: ...
    async def send_uploaded(self, chat: Any, handle: UploadedHandle, caption: str | None = None) -> Any: ...

ProgressCallback = Callable[[Progress], Any]

class _ProgressMeter:
    def __init__(self, total: int, direction: str, callback: ProgressCallback | None):
        self.total = total
        self.direction = direction
        self.callback = callback
        self.started = time.perf_counter()
        self.transferred = 0
        self.lock = asyncio.Lock()
        self.last_notification = 0.0

    async def add(self, count: int) -> None:
        async with self.lock:
            self.transferred += count
            if self.transferred > self.total:
                raise TransferError('transferred byte count exceeds source size')
            now = time.perf_counter()
            if self.callback is not None and (now - self.last_notification >= 0.25 or self.transferred == self.total):
                self.last_notification = now
                event = Progress(self.transferred, self.total, now - self.started, self.direction)
                response = self.callback(event)
                if inspect.isawaitable(response):
                    await response

    def result(self, value: Any) -> TransferResult:
        return TransferResult(self.transferred, time.perf_counter() - self.started, self.direction, value)

def _pwrite_fully(fd: int, data: bytes, offset: int) -> None:
    view = memoryview(data)
    while view:
        count = os.pwrite(fd, view, offset)
        if count <= 0:
            raise OSError('pwrite made no progress')
        offset += count
        view = view[count:]

def _md5(path: Path) -> str:
    h = hashlib.md5(usedforsecurity=False)
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def _first_error(group: BaseExceptionGroup) -> Exception:
    current: BaseException = group
    while isinstance(current, BaseExceptionGroup):
        current = current.exceptions[0]
    if isinstance(current, Exception):
        return current
    raise current

class TransferEngine:
    def __init__(self, backend: TransferBackend, options: TransferOptions | None = None):
        self.backend = backend
        self.options = options or TransferOptions()
        # Shared budget per engine/client, including opposite-direction jobs.
        # Four lanes by default, not an unchangeable global hard cap.
        self._slots = asyncio.Semaphore(max(self.options.download_workers, self.options.upload_workers))

    async def download(
        self,
        media: Any,
        size: int,
        destination: str | Path,
        *,
        progress: ProgressCallback | None = None,
        profile: bool = False,
    ) -> TransferResult:
        if not isinstance(size, int) or size <= 0:
            raise ValueError('known positive file size required for parallel download')
        path = Path(destination)
        if path.exists():
            raise FileExistsError(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + '.iqgram-' + secrets.token_hex(6) + '.part')
        chunk_size = self.options.download_request_size
        total_chunks = math.ceil(size / chunk_size)
        workers = min(self.options.download_workers, total_chunks)
        meter = _ProgressMeter(size, 'download', progress)
        worker_profiles: list[WorkerProfile] = []
        fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        try:
            os.ftruncate(fd, size)

            async def worker(index: int, begin: int, count: int) -> None:
                received = 0
                read_wait = 0.0
                disk_wait = 0.0
                transferred = 0
                async with self._slots:
                    stream = self.backend.iter_range(media, begin * chunk_size, count, chunk_size)
                    # Explicit anext allows observing time awaiting a media chunk.
                    # This includes queue/iterator overhead; it is NOT raw TCP RTT.
                    async with aclosing(aiter(stream)) as iterator:
                        while True:
                            before = time.perf_counter() if profile else 0.0
                            try:
                                data = await anext(iterator)
                            except StopAsyncIteration:
                                break
                            if profile:
                                read_wait += time.perf_counter() - before
                            if received >= count:
                                raise TransferError('backend returned extra download chunks')
                            offset = (begin + received) * chunk_size
                            expected = min(chunk_size, size - offset)
                            if len(data) != expected:
                                raise TransferError(f'bad chunk at {offset}: got {len(data)} bytes, expected {expected}')
                            before = time.perf_counter() if profile else 0.0
                            await asyncio.to_thread(_pwrite_fully, fd, data, offset)
                            if profile:
                                disk_wait += time.perf_counter() - before
                            await meter.add(len(data))
                            received += 1
                            transferred += len(data)
                if received != count:
                    raise TransferError(f'incomplete download range: {received}/{count} chunks')
                if profile:
                    worker_profiles.append(WorkerProfile(index, transferred, received, read_wait, disk_wait))

            try:
                async with asyncio.TaskGroup() as tasks:
                    start = 0
                    for index in range(workers):
                        count = total_chunks // workers + (1 if index < total_chunks % workers else 0)
                        tasks.create_task(worker(index, start, count))
                        start += count
            except ExceptionGroup as group:
                raise _first_error(group) from group
            if meter.transferred != size:
                raise TransferError('incomplete file')
            await asyncio.to_thread(os.fsync, fd)
            os.close(fd)
            fd = -1
            # Refuse overwriting a destination created by a competing process.
            # Linux hard-link provides atomic no-replace semantics.
            os.link(tmp, path)
            tmp.unlink()
            result = meter.result(path)
            if profile:
                result = replace(result, profile=DownloadProfile(tuple(sorted(worker_profiles, key=lambda x: x.worker_index))))
            return result
        finally:
            if fd >= 0:
                os.close(fd)
            tmp.unlink(missing_ok=True)

    async def upload(
        self,
        source: str | Path,
        chat: Any,
        *,
        caption: str | None = None,
        progress: ProgressCallback | None = None,
        media_kind: str = "document",
    ) -> TransferResult:
        path = Path(source)
        if not path.is_file():
            raise FileNotFoundError(path)
        # Validate native file semantics before uploading any byte.
        from .media import send_options
        send_options(UploadedHandle(0, 0, path.name, False, media_kind=media_kind))
        size = path.stat().st_size
        if size <= 0:
            raise ValueError('cannot upload an empty file')
        parts = math.ceil(size / CHUNK_SIZE)
        is_big = size > BIG_FILE_THRESHOLD
        checksum = None if is_big else await asyncio.to_thread(_md5, path)
        file_id = secrets.randbits(63)
        meter = _ProgressMeter(size, 'upload', progress)
        fd = os.open(path, os.O_RDONLY)
        try:
            queue: asyncio.Queue[int] = asyncio.Queue()
            for i in range(parts):
                queue.put_nowait(i)

            async def save_index(i: int, *, with_slot: bool) -> None:
                """Read one part and count it only after Telegram acknowledges it."""
                try:
                    expected = min(CHUNK_SIZE, size - i * CHUNK_SIZE)
                    chunk = await asyncio.to_thread(os.pread, fd, expected, i * CHUNK_SIZE)
                    if len(chunk) != expected:
                        raise TransferError('file changed or truncated during upload')
                    if with_slot:
                        async with self._slots:
                            acknowledged = await self.backend.save_part(file_id, i, parts, chunk, is_big)
                    else:
                        acknowledged = await self.backend.save_part(file_id, i, parts, chunk, is_big)
                    if not acknowledged:
                        raise TransferError(f'Telegram rejected file part {i}')
                    await meter.add(len(chunk))
                finally:
                    queue.task_done()

            async def worker() -> None:
                depth = self.options.upload_pipeline_depth
                if depth == 1:
                    # Preserve the original stable path for existing users.
                    while True:
                        try:
                            index = queue.get_nowait()
                        except asyncio.QueueEmpty:
                            return
                        await save_index(index, with_slot=True)
                else:
                    # One logical worker owns at most `depth` in-flight RPCs.
                    # Acquiring the shared slot for the worker's lifetime keeps
                    # the number of worker loops bounded, even across jobs.
                    async with self._slots:
                        async with asyncio.TaskGroup() as part_tasks:
                            pending: set[asyncio.Task[None]] = set()
                            while True:
                                while len(pending) < depth:
                                    try:
                                        index = queue.get_nowait()
                                    except asyncio.QueueEmpty:
                                        break
                                    pending.add(part_tasks.create_task(save_index(index, with_slot=False)))
                                if not pending:
                                    return
                                finished, pending = await asyncio.wait(
                                    pending, return_when=asyncio.FIRST_COMPLETED
                                )
                                # Propagate errors immediately. TaskGroup cancels
                                # any outstanding requests before returning.
                                for completed in finished:
                                    completed.result()

            try:
                async with asyncio.TaskGroup() as tasks:
                    for _ in range(min(self.options.upload_workers, parts)):
                        tasks.create_task(worker())
            except ExceptionGroup as group:
                raise _first_error(group) from group
            if meter.transferred != size:
                raise TransferError('incomplete upload')
            if path.stat().st_size != size:
                raise TransferError('file changed during upload')
            handle = UploadedHandle(file_id, parts, path.name, is_big, checksum, media_kind)
            sent = await self.backend.send_uploaded(chat, handle, caption)
            return meter.result(sent)
        finally:
            os.close(fd)
