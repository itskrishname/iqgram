"""IQGram: experimental Telegram media transfer library (no bot application)."""
from .transfer import (
    Progress, TransferEngine, TransferError, TransferOptions, TransferResult,
    UploadedHandle,
)

__version__ = '0.3.1'

# Importing IQGram core does not require Telegram dependencies installed.
# The live MTProto adapter is loaded when a Client is instantiated.

def __getattr__(name: str):
    if name == 'Client':
        from .client import Client
        return Client
    raise AttributeError(name)

__all__ = ['Client', 'Progress', 'TransferEngine', 'TransferError', 'TransferOptions', 'TransferResult', 'UploadedHandle']
