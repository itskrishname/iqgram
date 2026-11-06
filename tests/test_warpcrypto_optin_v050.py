"""Use fakes for opt-in activation; actual native wheel parity needs live install."""
import sys
from types import ModuleType

import pytest

import iqgram.crypto as crypto


class FakeAES:
    @staticmethod
    def encrypt_ige(data, key, iv):
        return data[::-1]
    @staticmethod
    def decrypt_ige(data, key, iv):
        return data[::-1]


def install_modules(monkeypatch, good=True):
    aes_module=ModuleType('telethon.crypto.aes')
    aes_module.AES=type('TestAES', (FakeAES,), {})
    warp=ModuleType('warpcrypto')
    warp.ige256_encrypt = lambda data, key, iv: data[::-1] if good else b'invalid'
    warp.ige256_decrypt = lambda data, key, iv: data[::-1]
    monkeypatch.setitem(sys.modules,'telethon.crypto.aes',aes_module)
    monkeypatch.setitem(sys.modules,'warpcrypto',warp)
    monkeypatch.setattr(crypto,'_ENABLED',False)
    return aes_module.AES


def test_opt_in_enables_only_after_parity_check(monkeypatch):
    AES=install_modules(monkeypatch,good=True)
    assert crypto.enable_warpcrypto() == 'warpcrypto'
    assert crypto._ENABLED is True
    encrypted=AES.encrypt_ige(b'a'*16,b'k'*32,b'i'*32)
    assert AES.decrypt_ige(encrypted,b'k'*32,b'i'*32) == b'a'*16
    assert crypto.enable_warpcrypto() == 'warpcrypto'


def test_opt_in_rejects_mismatch_without_changing_crypto(monkeypatch):
    AES=install_modules(monkeypatch,good=False)
    original=AES.encrypt_ige
    with pytest.raises(RuntimeError,match='compatibility'):
        crypto.enable_warpcrypto()
    assert AES.encrypt_ige is original
    assert crypto._ENABLED is False


def test_opt_in_encrypt_pads_to_full_aes_block(monkeypatch):
    AES=install_modules(monkeypatch,good=True)
    crypto.enable_warpcrypto()
    encrypted=AES.encrypt_ige(b'a'*13,b'k'*32,b'i'*32)
    assert len(encrypted) == 16
    assert AES.decrypt_ige(encrypted,b'k'*32,b'i'*32)[:13] == b'a'*13
