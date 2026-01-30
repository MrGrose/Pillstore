from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from app.core.config import templates
from app.services.cart import get_cart_count
from app.core.security import get_current_user_optional
from app.models.users import User

router = APIRouter()


@router.get("/access-denied", response_class=HTMLResponse)
async def access_denied(
    request: Request,
    current_user: User | None = Depends(get_current_user_optional),
    cart_count: int = Depends(get_cart_count),
):
    return templates.TemplateResponse(
        "errors/403.html",
        {"request": request, "current_user": current_user, "cart_count": cart_count},
    )


@router.get("/admin/error-404", response_class=HTMLResponse)
async def admin_error_404(
    request: Request,
    title: str = Query("Не найдено"),
    message: str = Query(""),
    tab: str = Query("dashboard"),
    current_user: User | None = Depends(get_current_user_optional),
    cart_count: int = Depends(get_cart_count),
):
    return templates.TemplateResponse(
        "errors/admin_error.html",
        {
            "request": request,
            "current_user": current_user,
            "cart_count": cart_count,
            "code": 404,
            "title": title,
            "message": message,
            "tab": tab,
        },
    )


@router.get("/admin/error-400", response_class=HTMLResponse)
async def admin_error_400(
    request: Request,
    title: str = Query("Ошибка"),
    message: str = Query(""),
    tab: str = Query("dashboard"),
    current_user: User | None = Depends(get_current_user_optional),
    cart_count: int = Depends(get_cart_count),
):
    return templates.TemplateResponse(
        "errors/admin_error.html",
        {
            "request": request,
            "current_user": current_user,
            "cart_count": cart_count,
            "code": 400,
            "title": title,
            "message": message,
            "tab": tab,
        },
    )
