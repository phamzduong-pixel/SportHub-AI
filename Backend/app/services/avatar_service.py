from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..core.config import settings
ALLOWED_MIME = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp'}


def _detected_mime(content: bytes) -> str | None:
    if content.startswith(b'\x89PNG\r\n\x1a\n') and b'IEND' in content[-64:]:
        return 'image/png'
    if content.startswith(b'\xff\xd8\xff') and content.endswith(b'\xff\xd9'):
        return 'image/jpeg'
    if len(content) >= 16 and content[:4] == b'RIFF' and content[8:12] == b'WEBP' and content[12:16] in (b'VP8 ', b'VP8L', b'VP8X'):
        return 'image/webp'
    return None

AVATAR_URL_PREFIX = '/api/auth/avatars/'


async def store_avatar(upload: UploadFile) -> tuple[str, str]:
    declared = (upload.content_type or '').lower()
    content = await upload.read(settings.AVATAR_MAX_BYTES + 1)
    if len(content) > settings.AVATAR_MAX_BYTES:
        raise HTTPException(status_code=413, detail='Ảnh đại diện không được vượt quá 5 MB')
    actual = _detected_mime(content)
    if actual is None or actual not in ALLOWED_MIME or declared != actual:
        raise HTTPException(status_code=415, detail='Ảnh đại diện phải là tệp JPG, PNG hoặc WEBP hợp lệ')
    root = settings.AVATAR_DIR
    root.mkdir(parents=True, exist_ok=True)
    file_name = f'{uuid4().hex}{ALLOWED_MIME[actual]}'
    target = (root / file_name).resolve()
    if root not in target.parents:
        raise HTTPException(status_code=400, detail='Đường dẫn ảnh đại diện không hợp lệ')
    target.write_bytes(content)
    return file_name, f'{AVATAR_URL_PREFIX}{file_name}'


def delete_local_avatar(avatar_url: str | None):
    if not avatar_url or not avatar_url.startswith(AVATAR_URL_PREFIX):
        return
    file_name = Path(avatar_url.removeprefix(AVATAR_URL_PREFIX)).name
    root = settings.AVATAR_DIR
    target = (root / file_name).resolve()
    if root in target.parents and target.is_file():
        target.unlink()


def avatar_response(file_name: str):
    safe_name = Path(file_name).name
    if safe_name != file_name:
        raise HTTPException(status_code=404, detail='Không tìm thấy ảnh đại diện')
    root = settings.AVATAR_DIR
    target = (root / safe_name).resolve()
    if root not in target.parents or not target.is_file():
        raise HTTPException(status_code=404, detail='Không tìm thấy ảnh đại diện')
    mime = {'.jpg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}.get(target.suffix.lower())
    if mime is None:
        raise HTTPException(status_code=404, detail='Không tìm thấy ảnh đại diện')
    return FileResponse(target, media_type=mime, headers={
        'Cache-Control': 'public, max-age=31536000, immutable',
        'X-Content-Type-Options': 'nosniff', 'Content-Disposition': 'inline',
    })
