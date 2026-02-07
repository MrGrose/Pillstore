import aiohttp
import aiofiles
import uuid
import re

from pathlib import Path
from mimetypes import guess_extension
from fastapi import status, HTTPException, UploadFile

from app.models.products import Product


BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEDIA_ROOT = BASE_DIR / "media" / "products"
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 2 * 1024 * 1024


async def save_product_image(file: UploadFile) -> str:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Разрешены изображения в формате JPG, PNG или WebP",
        )

    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image is too large",
        )

    extension = Path(file.filename or "").suffix.lower() or ".jpg"
    file_name = f"{uuid.uuid4()}{extension}"
    file_path = MEDIA_ROOT / file_name
    file_path.write_bytes(content)

    return f"/media/products/{file_name}"


def remove_product_image(url: str | None) -> None:
    if not url:
        return
    relative_path = url.lstrip("/")
    file_path = BASE_DIR / relative_path
    if file_path.exists():
        file_path.unlink()


async def save_image_from_url(image_url: str) -> str | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                image_url, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    return None
                content = await resp.read()

        if len(content) > MAX_IMAGE_SIZE:
            return None

        content_type = resp.headers.get("content-type", "").lower()
        if not content_type.startswith("image/"):
            return None
        if content_type not in ALLOWED_IMAGE_TYPES:
            return None

        extension = guess_extension(content_type) or ".jpg"
        file_name = f"{uuid.uuid4()}{extension}"
        file_path = MEDIA_ROOT / file_name

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        return f"/media/products/{file_name}"
    except Exception:
        return None


async def formatted_description(product: Product) -> dict:
    if not (product.description_left and product.description_right):
        return {}

    cleaned_parts = {}
    pattern_left = r"(^Описание.+?)(Рекомендации.+?)(Другие ингредиенты.+?|Ингредиенты.+?)(Предупреждения.+?)(Отказ от ответственности.+)"
    pattern_right = r"\s+(?=[А-Я])"
    text_left = re.search(
        pattern_left, product.description_left, re.MULTILINE | re.DOTALL
    )
    text_right = product.description_right.replace("‡", "").replace("**", "")
    if text_left:
        section_names = [
            "Описание",
            "Рекомендации по применению",
            "Другие ингредиенты",
            "Предупреждения",
            "Отказ от ответственности",
        ]
        for i in range(1, 6):
            group_text = text_left.group(i)
            section_name = section_names[i - 1]
            content_left = group_text[len(section_name):].strip()
            cleaned_parts[section_name] = [content_left]

    if text_right:
        text_right = (
            product.description_right.replace("‡", "")
            .replace("**", "")
            .replace("† †", "")
        )
        content_right = re.split(pattern_right, text_right, re.MULTILINE)
        cleaned_parts["Пищевая ценность"] = content_right[1:]

    return cleaned_parts
