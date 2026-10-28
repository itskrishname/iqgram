import asyncio
import pytest
from iqgram.queue import JobStore, TransferQueue


def test_persistence_and_idempotent_cancel(tmp_path):
    db = tmp_path/'jobs.db'
    store = JobStore(db)
    jid = store.enqueue('download', 444, 8, 123)
    assert store.get(jid)['status'] == 'queued'
    store.close()
    again = JobStore(db)
    assert again.get(jid)['message_id'] == 8
    assert again.cancel(jid, 123)
    assert again.get(jid)['status'] == 'cancelled'
    assert not again.cancel(jid, 456)
    again.close()


def test_restart_marks_running_interrupted_not_replayed(tmp_path):
    store=JobStore(tmp_path/'jobs.db')
    jid=store.enqueue('mirror', 1, 2, 3)
    store.set_status(jid, 'running')
    store.recover()
    assert store.get(jid)['status'] == 'interrupted'
    assert store.retry(jid, 3)
    assert store.get(jid)['status'] == 'queued'
    store.close()


@pytest.mark.asyncio
async def test_worker_download_updates_finished_job(tmp_path):
    class FakeClient:
        async def get_messages(self, chat_id, message_id, replies=0):
            return type('Message', (), {'document': object()})()
        async def download_media(self, message, file_name=None, progress=None):
            p=__import__('pathlib').Path(file_name)/'got.bin'
            p.write_bytes(b'hello')
            await progress(5, 5)
            return str(p)
        def stop_transmission(self):
            raise RuntimeError('cancelled')
    store=JobStore(tmp_path/'jobs.db')
    queue=TransferQueue(FakeClient(), store, tmp_path/'downloads', workers=1)
    await queue.start()
    jid=await queue.enqueue('download', chat_id=44, message_id=9, owner_id=333)
    await asyncio.wait_for(queue.wait(jid), timeout=3)
    assert store.get(jid)['status'] == 'completed'
    assert store.get(jid)['bytes_done'] == 5
    await queue.stop()
    store.close()


@pytest.mark.asyncio
async def test_successful_mirror_survives_cleanup_failure(tmp_path):
    from pathlib import Path
    from types import SimpleNamespace
    class FakeClient:
        async def get_messages(self, *args, **kwargs):
            return SimpleNamespace(document=SimpleNamespace(file_size=4))
        async def download_media(self, message, file_name=None, progress=None):
            folder = Path(file_name)
            path = folder / 'video.mkv'
            path.write_bytes(b'data')
            # Another artifact is intentionally left in job folder to prevent rmdir.
            (folder / 'preview.tmp').write_bytes(b'preview')
            await progress(4, 4)
            return str(path)
        async def send_document(self, chat_id, document, caption=None, progress=None):
            await progress(4,4)
            return SimpleNamespace(id=99)
    store = JobStore(tmp_path / 'jobs.db')
    queue = TransferQueue(FakeClient(), store, tmp_path/'downloads', delete_after_mirror=True)
    await queue.start()
    jid = await queue.enqueue('mirror','me',1,300)
    row=await asyncio.wait_for(queue.wait(jid),3)
    assert row['status']=='completed'
    assert 'Message #99' in row['result']
    await queue.stop()
    store.close()
