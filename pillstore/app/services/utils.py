import aiohttp
import aiofiles
import uuid

from pathlib import Path
from mimetypes import guess_extension
from fastapi import status, HTTPException, UploadFile



BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEDIA_ROOT = BASE_DIR / "media" / "products"
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 2 * 1024 * 1024


async def save_product_image(file: UploadFile) -> str:
    """
    Сохраняет изображение товара и возвращает относительный URL.
    """
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Разрешены изображения в формате JPG, PNG или WebP")

    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Image is too large")

    extension = Path(file.filename or "").suffix.lower() or ".jpg"
    file_name = f"{uuid.uuid4()}{extension}"
    file_path = MEDIA_ROOT / file_name
    file_path.write_bytes(content)

    return f"/media/products/{file_name}"


def remove_product_image(url: str | None) -> None:
    """
    Удаляет файл изображения, если он существует.
    """
    if not url:
        return
    relative_path = url.lstrip("/")
    file_path = BASE_DIR / relative_path
    if file_path.exists():
        file_path.unlink()
        

async def save_image_from_url(image_url: str) -> str | None:
    """
    Скачивает и сохраняет изображение из URL (для bulk-импорта).
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return None
                content = await resp.read()
        
        if len(content) > MAX_IMAGE_SIZE:
            return None
        
        content_type = resp.headers.get('content-type', '').lower()
        if not content_type.startswith('image/'):
            return None
        if content_type not in ALLOWED_IMAGE_TYPES:
            return None
        
        extension = guess_extension(content_type) or '.jpg'
        file_name = f"{uuid.uuid4()}{extension}"
        file_path = MEDIA_ROOT / file_name
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        return f"/media/products/{file_name}"
    except Exception:
        return None
    
