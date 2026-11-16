"""Pure byte, media-type/size and burst-timing helpers."""
from __future__ import annotations
import datetime as dt
import hashlib
import io
__all__ = ['BURST_QUIET_SECONDS', 'MAX_MEDIA_BYTES', 'ACCEPTED_MIME', 'content_hash', 'is_accepted_media', 'strip_location_metadata', 'burst_is_closed']
BURST_QUIET_SECONDS = 90
MAX_MEDIA_BYTES = 25 * 1024 * 1024
ACCEPTED_MIME = frozenset({'image/jpeg', 'image/png', 'image/heic', 'image/heif', 'image/webp', 'video/mp4', 'video/quicktime'})

def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def is_accepted_media(mime_type: str, size_bytes: int) -> tuple[bool, str]:
    if mime_type not in ACCEPTED_MIME:
        return (False, 'that file type will not go through — a photo or video works best')
    if size_bytes <= 0:
        return (False, 'that came through empty — worth sending again')
    if size_bytes > MAX_MEDIA_BYTES:
        return (False, 'that one is too big to send — a shorter video should work')
    return (True, '')

def strip_location_metadata(data: bytes, mime_type: str) -> bytes:
    if not mime_type.startswith('image/'):
        return data
    try:
        from PIL import Image
    except ImportError:
        raise
    try:
        with Image.open(io.BytesIO(data)) as img:
            clean = Image.new(img.mode, img.size)
            clean.paste(img)
            out = io.BytesIO()
            clean.save(out, format=img.format or 'JPEG')
            return out.getvalue()
    except Exception:
        raise ValueError('image could not be re-encoded; refusing to store it unstripped') from None

def burst_is_closed(last_message_at: dt.datetime, now: dt.datetime) -> bool:
    return (now - last_message_at).total_seconds() >= BURST_QUIET_SECONDS
