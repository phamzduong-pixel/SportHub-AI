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


async def store_document(upload: UploadFile) -> dict:
    declared = (upload.content_type or '').lower()
    content = await upload.read(settings.PARTNER_DOCUMENT_MAX_BYTES + 1)
    if len(content) > settings.PARTNER_DOCUMENT_MAX_BYTES:
        raise HTTPException(status_code=413, detail='Ảnh giấy tờ vượt quá dung lượng tối đa 5 MB')
    actual = _detected_mime(content)
    if actual is None or actual not in ALLOWED_MIME or declared != actual:
        raise HTTPException(status_code=415, detail='Ảnh giấy tờ phải là tệp JPG, PNG hoặc WEBP hợp lệ')
    root = settings.PARTNER_DOCUMENT_DIR
    root.mkdir(parents=True, exist_ok=True)
    file_name = f'{uuid4().hex}{ALLOWED_MIME[actual]}'
    target = (root / file_name).resolve()
    if root not in target.parents:
        raise HTTPException(status_code=400, detail='Đường dẫn tệp không hợp lệ')
    target.write_bytes(content)
    return {
        'document_path': file_name, 'document_mime': actual,
        'document_original_name': Path(upload.filename or 'giay-to').name[:255],
        'document_size': len(content),
    }


def delete_document(path_value: str | None):
    if not path_value:
        return
    root = settings.PARTNER_DOCUMENT_DIR
    target = (root / path_value).resolve()
    if root in target.parents and target.is_file():
        target.unlink()


def document_response(path_value: str | None, mime: str | None):
    if not path_value:
        raise HTTPException(status_code=404, detail='Hồ sơ chưa có ảnh giấy tờ')
    root = settings.PARTNER_DOCUMENT_DIR
    target = (root / path_value).resolve()
    if root not in target.parents or not target.is_file():
        raise HTTPException(status_code=404, detail='Không tìm thấy ảnh giấy tờ')
    return FileResponse(target, media_type=mime or 'application/octet-stream', headers={
        'Cache-Control': 'private, no-store, max-age=0', 'X-Content-Type-Options': 'nosniff',
        'Content-Disposition': 'inline',
    })
