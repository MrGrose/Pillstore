from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_seller
from app.models.users import User
from app.services.product_service import ProductService

router = APIRouter(prefix="/admin")


@router.post("/products/iherb-import")
async def iherb_import(
    url: str = Form(...),
    tab: str = Form("products"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    product_service = ProductService(db)
    message, msg_type = await product_service.import_iherb_product(url, current_user)

    return RedirectResponse(
        f"/admin?tab={tab}&message={message.replace(' ', '+')}&message_type={msg_type}",
        status_code=303,
    )
