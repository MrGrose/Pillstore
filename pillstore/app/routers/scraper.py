from fastapi import APIRouter, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_redirect import redirect_admin
from app.core.deps import get_db
from app.core.security import get_current_seller
from app.models.users import User
from app.services.product_service import ProductService

router = APIRouter(prefix="/admin")


def _normalize_iherb_url(url: str) -> str:
    url = (url or "").strip()
    if url and not url.startswith(("http://", "https://")):
        return f"https://{url}"
    return url


@router.post("/products/iherb-import")
async def iherb_import(
    url: str = Form(...),
    tab: str = Form("products"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    url = _normalize_iherb_url(url)
    product_service = ProductService(db)
    message, msg_type = await product_service.import_iherb_product(url, current_user)
    return redirect_admin(tab, message=message, message_type=msg_type)
