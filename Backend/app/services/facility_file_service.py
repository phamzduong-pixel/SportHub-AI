from pathlib import Path
from uuid import uuid4
from hashlib import sha256

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..core.config import settings

IMAGE_MIME = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp'}
DOCUMENT_MIME = {'image/jpeg': '.jpg', 'image/png': '.png', 'application/pdf': '.pdf'}
MIME_EXTENSIONS = {
    'image/jpeg': {'.jpg', '.jpeg'}, 'image/png': {'.png'},
    'image/webp': {'.webp'}, 'application/pdf': {'.pdf'},
}


def detected_mime(content: bytes) -> str | None:
    if content.startswith(b'%PDF-'):
        return 'application/pdf'
    if content.startswith(b'\x89PNG\r\n\x1a\n') and b'IEND' in content[-64:]:
        return 'image/png'
    if content.startswith(b'\xff\xd8\xff') and content.endswith(b'\xff\xd9'):
        return 'image/jpeg'
    if len(content) >= 16 and content[:4] == b'RIFF' and content[8:12] == b'WEBP':
        return 'image/webp'
    return None


async def store_facility_file(upload: UploadFile, facility_id: int, private: bool) -> dict:
    allowed = DOCUMENT_MIME if private else IMAGE_MIME
    limit = settings.FACILITY_DOCUMENT_MAX_BYTES if private else settings.FACILITY_IMAGE_MAX_BYTES
    content = await upload.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(status_code=413, detail='Tệp vượt quá dung lượng cho phép')
    actual = detected_mime(content)
    original_suffix = Path(upload.filename or '').suffix.lower()
    if actual not in allowed or (upload.content_type or '').lower() != actual or original_suffix not in MIME_EXTENSIONS.get(actual, set()):
        raise HTTPException(status_code=415, detail='Định dạng tệp không hợp lệ')
    root = (settings.FACILITY_PRIVATE_DIR if private else settings.FACILITY_IMAGE_DIR).resolve()
    folder = (root / str(facility_id)).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if root not in folder.parents:
        raise HTTPException(status_code=400, detail='Đường dẫn lưu tệp không hợp lệ')
    folder.mkdir(parents=True, exist_ok=True)
    file_name = uuid4().hex + allowed[actual]
    target = (folder / file_name).resolve()
    target.write_bytes(content)
    return {
        'file_path': str(Path(str(facility_id)) / file_name),
        'original_name': Path(upload.filename or 'file').name[:255],
        'mime_type': actual,
        'file_size': len(content),
        **({'file_sha256': sha256(content).hexdigest()} if private else {}),
    }


def remove_facility_file(path_value: str | None, private: bool):
    if not path_value:
        return
    root = (settings.FACILITY_PRIVATE_DIR if private else settings.FACILITY_IMAGE_DIR).resolve()
    target = (root / path_value).resolve()
    if root in target.parents and target.is_file():
        target.unlink()


def facility_file_response(path_value: str, mime: str, private: bool):
    root = (settings.FACILITY_PRIVATE_DIR if private else settings.FACILITY_IMAGE_DIR).resolve()
    target = (root / path_value).resolve()
    if root not in target.parents or not target.is_file():
        raise HTTPException(status_code=404, detail='Không tìm thấy tệp')
    cache = 'private, no-store' if private else 'public, max-age=86400'
    headers = {'Cache-Control': cache, 'X-Content-Type-Options': 'nosniff', 'Content-Disposition': 'inline'}
    if private:
        headers['Content-Security-Policy'] = 'sandbox'
    return FileResponse(target, media_type=mime, headers=headers)
def facility_image_response(path_value: str, mime: str, public_cache: bool):
    root = settings.FACILITY_IMAGE_DIR.resolve()
    target = (root / path_value).resolve()
    if root not in target.parents or not target.is_file():
        raise HTTPException(status_code=404, detail='Không tìm thấy ảnh')
    cache = 'public, max-age=86400' if public_cache else 'private, no-store, max-age=0'
    return FileResponse(target, media_type=mime, headers={
        'Cache-Control': cache, 'X-Content-Type-Options': 'nosniff', 'Content-Disposition': 'inline',
    })
