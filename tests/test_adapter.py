import asyncio
import sys
from types import ModuleType, SimpleNamespace

from iqgram.telethon_adapter import TelethonBackend
from iqgram.transfer import UploadedHandle

class TelegramStub:
    def __init__(self): self.requests=[];self.sent=[];self.iter_args=[];self.closed=False
    def iter_download(self, media, **kwargs):
        self.iter_args.append((media, kwargs))
        parent = self
        class Iter:
            def __aiter__(self): return self
            async def __anext__(self):
                if getattr(self,'already',False): raise StopAsyncIteration
                self.already=True
                return memoryview(b'chunk')
            async def close(self): parent.closed=True
        return Iter()
    async def __call__(self, request):
        self.requests.append(request)
        return True
    async def send_file(self, chat, file, **kw):
        self.sent.append((chat,file,kw))
        return 'sent'


def test_telethon_adapter_calls_correct_transfer_methods(monkeypatch):
    class SmallReq:
        def __init__(self,*args): self.args=args
    class BigReq:
        def __init__(self,*args): self.args=args
    class SmallHandle:
        def __init__(self,*args):self.args=args
    class BigHandle:
        def __init__(self,*args):self.args=args
    modules={
        'telethon':ModuleType('telethon'),
        'telethon.tl':ModuleType('telethon.tl'),
        'telethon.tl.functions':ModuleType('telethon.tl.functions'),
        'telethon.tl.functions.upload':ModuleType('telethon.tl.functions.upload'),
        'telethon.tl.types':ModuleType('telethon.tl.types'),
    }
    modules['telethon.tl.functions.upload'].SaveBigFilePartRequest=BigReq
    modules['telethon.tl.functions.upload'].SaveFilePartRequest=SmallReq
    modules['telethon.tl.types'].InputFile=SmallHandle
    modules['telethon.tl.types'].InputFileBig=BigHandle
    for key, value in modules.items(): monkeypatch.setitem(sys.modules,key,value)
    async def run():
        tg=TelegramStub();backend=TelethonBackend(tg)
        data=[x async for x in backend.iter_range('MEDIA',512*1024,1,512*1024)]
        assert data==[b'chunk']
        assert tg.closed
        assert tg.iter_args[0][1]['offset']==512*1024
        await backend.save_part(22,1,3,b'abc',False)
        await backend.save_part(22,1,3,b'abc',True)
        assert isinstance(tg.requests[0],SmallReq)
        assert isinstance(tg.requests[1],BigReq)
        assert tg.requests[1].args[2]==3
        await backend.send_uploaded('me',UploadedHandle(1,2,'x.txt',False,'a'*32),'Hi')
        await backend.send_uploaded('me',UploadedHandle(2,21,'big.mkv',True),None)
        assert isinstance(tg.sent[0][1],SmallHandle)
        assert isinstance(tg.sent[1][1],BigHandle)
        assert tg.sent[0][2]['force_document'] is True
    asyncio.run(run())
