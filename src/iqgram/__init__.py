"""IQGram: experimental Telegram media transfer library (no bot application)."""
from .transfer import (
    Progress, TransferEngine, TransferError, TransferOptions, TransferResult,
    UploadedHandle, WorkerProfile, DownloadProfile,
)

__version__ = '0.5.0'

# Importing IQGram core does not require Telegram dependencies installed.
# The live MTProto adapter is loaded when a Client is instantiated.

def __getattr__(name: str):
    if name == 'Client':
        from .client import Client
        return Client
    if name == 'enable_warpcrypto':
        from .crypto import enable_warpcrypto
        return enable_warpcrypto
    raise AttributeError(name)

__all__ = ['Client', 'Progress', 'TransferEngine', 'TransferError', 'TransferOptions', 'TransferResult', 'UploadedHandle', 'WorkerProfile', 'DownloadProfile', 'enable_warpcrypto']
