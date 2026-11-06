"""Telegram native file media selection.

Any file extension is transferable as a *document*. Native Telegram media
semantics (photo, voice, sticker etc.) impose additional format constraints.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .transfer import UploadedHandle

MEDIA_KINDS = frozenset({
    'document', 'auto', 'photo', 'video', 'audio', 'voice',
    'video_note', 'animation', 'sticker',
})
PHOTOS = {'.jpg', '.jpeg', '.png'}
VIDEOS = {'.mp4', '.m4v', '.mov', '.mkv', '.webm', '.avi', '.ts', '.3gp', '.flv'}
AUDIO = {'.mp3', '.m4a', '.aac', '.ogg', '.oga', '.opus', '.flac', '.wav', '.wma', '.alac', '.aiff', '.amr'}
VOICE = {'.ogg', '.opus'}
ANIMATIONS = {'.gif', '.mp4'}
STICKERS = {'.webp', '.webm', '.tgs'}


def send_options(handle: UploadedHandle) -> dict[str, object]:
    """Return Telethon send_file flags, preserving document as safe default.

    For generic documents all file extensions/unknown MIME types work.
    Native message types require Telegram-compatible files and may require
    additional metadata (e.g. sticker set, duration) from the caller.
    """
    kind = handle.media_kind
    ext = Path(handle.name).suffix.lower()
    if kind not in MEDIA_KINDS:
        raise ValueError(f'unsupported media_kind: {kind!r} (use document or auto for arbitrary files)')
    if kind == 'auto':
        if ext in PHOTOS:
            kind = 'photo'
        elif ext == '.mp4':
            kind = 'video'
        elif ext in AUDIO:
            kind = 'audio'
        else:
            kind = 'document'

    constraints = {
        'photo': PHOTOS, 'video': VIDEOS, 'audio': AUDIO,
        'voice': VOICE, 'video_note': {'.mp4'},
        'animation': ANIMATIONS, 'sticker': STICKERS,
    }
    if kind in constraints and ext not in constraints[kind]:
        raise ValueError(f'media_kind={kind!r} requires a compatible extension, got {ext or "none"!r}')

    flags: dict[str, object] = {'force_document': kind == 'document'}
    if kind == 'video' and ext == '.mp4':
        flags['supports_streaming'] = True
    elif kind == 'voice':
        flags['voice_note'] = True
    elif kind == 'video_note':
        flags['video_note'] = True
    elif kind == 'sticker':
        flags['mime_type'] = {
            '.webp': 'image/webp',
            '.webm': 'video/webm',
            '.tgs': 'application/x-tgsticker',
        }[ext]
    return flags
