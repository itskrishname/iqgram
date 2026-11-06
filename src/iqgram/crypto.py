"""Experimental, explicitly opt-in WarpCrypto acceleration for Telethon AES-IGE.

This patches the *process-wide* Telethon AES helper, after checking known
aligned plaintext/ciphertext parity against the already installed provider
(usually cryptg). It is not an MTProto transport implementation. Do not
activate after creating other Telethon clients in the same process.
"""
from __future__ import annotations

import importlib
import os

_ENABLED = False


def enable_warpcrypto() -> str:
    """Enable WarpCrypto AES-IGE at process startup (experimental).

    Raises ImportError if dependencies are missing, or RuntimeError if the
    selected wheel fails compatibility checks. Nothing is patched on error.
    """
    global _ENABLED
    if _ENABLED:
        return 'warpcrypto'
    try:
        warp = importlib.import_module('warpcrypto')
    except ImportError as exc:
        raise ImportError('WarpCrypto is optional: install it with pip install WarpCrypto') from exc
    from telethon.crypto.aes import AES

    original_encrypt = AES.encrypt_ige
    original_decrypt = AES.decrypt_ige
    # Compare ciphertext against Telethon's existing (typically cryptg)
    # implementation for multiple data lengths and random key/IV pairs.
    for size in (16, 64, 512, 4096):
        key, iv, plain = os.urandom(32), os.urandom(32), os.urandom(size)
        reference = original_encrypt(plain, key, iv)
        candidate = warp.ige256_encrypt(plain, key, iv)
        if candidate != reference or warp.ige256_decrypt(candidate, key, iv) != plain:
            raise RuntimeError('WarpCrypto compatibility test failed; original Telethon crypto unchanged')
        if original_decrypt(candidate, key, iv) != plain:
            raise RuntimeError('WarpCrypto compatibility test failed; original Telethon crypto unchanged')

    def encrypt_ige(data: bytes, key: bytes, iv: bytes) -> bytes:
        # Match Telethon's padding behavior for non-block-aligned inputs.
        if len(data) % 16:
            data += os.urandom(16 - len(data) % 16)
        return warp.ige256_encrypt(data, key, iv)

    def decrypt_ige(data: bytes, key: bytes, iv: bytes) -> bytes:
        return warp.ige256_decrypt(data, key, iv)

    # Telethon imports AES as a class; replacing its static methods makes it
    # effective for the current process. This is intentionally opt-in only.
    AES.encrypt_ige = staticmethod(encrypt_ige)
    AES.decrypt_ige = staticmethod(decrypt_ige)
    _ENABLED = True
    return 'warpcrypto'
