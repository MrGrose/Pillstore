from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.config import templates

from app.models.users import User
from app.core.security import get_current_user

from app.services.profile_service import ProfileService

router = APIRouter()


@router.get("/", response_class=HTMLResponse, name="profile_page")
async def profile_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile_svc = ProfileService(db)
    orders = await profile_svc.get_orders_profile(current_user)

    return templates.TemplateResponse(
        "/profile/profile.html",
        {
            "current_user": current_user,
            "orders": orders,
            "request": request,
            "cart_count": 0,
        },
    )
