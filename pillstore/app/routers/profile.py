from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.deps import get_db
from app.models.orders import Order
from app.core.config import templates

from app.models.users import User as UserModel
from app.core.security import get_current_user

router = APIRouter(tags=["Profile"])


@router.get("/", response_class=HTMLResponse, name="profile_page")
async def profile_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    db_orders = await db.scalars(
        select(Order).where(Order.user_id == current_user.id)
    )
    orders = list(db_orders.all())

    return templates.TemplateResponse(
        "/profile/profile.html", 
        {
            "current_user": current_user,
            "orders": orders,
            "request": request,
            "cart_count": 0,
        }
    )
