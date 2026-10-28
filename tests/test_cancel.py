import pytest
import asyncio
from pathlib import Path
from iqgram.queue import JobStore, TransferQueue


@pytest.mark.asyncio
async def test_queued_cancel_does_not_run(tmp_path):
    store=JobStore(tmp_path/'jobs.db')
    class NoCalls:
        async def get_messages(self,*args,**kwargs):
            raise AssertionError('Cancelled job was unexpectedly started')
    q=TransferQueue(NoCalls(),store,tmp_path/'dl')
    jid=store.enqueue('download','me',5,5)
    assert store.cancel(jid,5)
    await q.start()
    assert store.get(jid)['status']=='cancelled'
    await q.stop()
    store.close()


@pytest.mark.asyncio
async def test_worker_marks_unavailable_message_failed(tmp_path):
    store=JobStore(tmp_path/'jobs.db')
    class MissingMedia:
        async def get_messages(self,*args,**kwargs):
            return None
    q=TransferQueue(MissingMedia(),store,tmp_path/'dl')
    await q.start()
    jid=await q.enqueue('download','me',1,123)
    row=await asyncio.wait_for(q.wait(jid),3)
    assert row['status']=='failed'
    assert 'downloadable' in row['error']
    await q.stop()
    store.close()


@pytest.mark.asyncio
async def test_shutdown_does_not_replace_explicit_cancelled_status(tmp_path):
    class SlowClient:
        async def get_messages(self,*args,**kwargs):
            return type('Message', (), {'document': object()})()
        async def download_media(self, message, file_name=None, progress=None):
            await asyncio.Event().wait()
    store=JobStore(tmp_path/'jobs.db')
    q=TransferQueue(SlowClient(),store,tmp_path/'downloads')
    await q.start()
    jid=await q.enqueue('download','me',1,777)
    for _ in range(100):
        if store.get(jid)['status']=='running':
            break
        await asyncio.sleep(.001)
    assert store.get(jid)['status']=='running'
    assert store.cancel(jid,777)
    await q.stop()
    assert store.get(jid)['status']=='cancelled'
    store.close()
