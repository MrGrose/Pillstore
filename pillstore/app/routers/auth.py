from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings, templates
from app.core.deps import get_db
from app.services.user_service import UserService


auth_router = APIRouter(prefix="/auth")


@auth_router.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("/auth/login.html", {"request": request})


@auth_router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user_svc = UserService(db)
    errors = await user_svc.validate_login_data(email, password)
    if errors:
        return templates.TemplateResponse(
            "auth/login.html", {"request": request, "errors": errors, "email": email}
        )
    access_token = await user_svc.authenticate_user(email, password)
    response = RedirectResponse("/products", status_code=303)
    response.set_cookie(
        "access_token",
        access_token,
        httponly=True,
        max_age=settings.MAX_AGE,
        secure=(settings.ENV == "production"),
        samesite="lax",
    )
    return response


@auth_router.post("/logout")
async def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("access_token")
    return response


@auth_router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(
        "/auth/register.html",
        {"request": request, "errors": []},
    )


@auth_router.post("/register")
async def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
    role: str = Form("buyer"),
):
    user_svc = UserService(db)
    errors = await user_svc.validate_register_data(email, password)
    if errors:
        return templates.TemplateResponse(
            "auth/register.html", {"request": request, "errors": errors, "email": email}
        )
    _, access_token = await user_svc.register_user_and_issue_token(
        email, password, role
    )
    response = RedirectResponse("/products?msg=registered", status_code=303)
    response.set_cookie(
        "access_token",
        access_token,
        httponly=True,
        max_age=settings.MAX_AGE,
        secure=(settings.ENV == "production"),
        samesite="lax",
    )
    return response


@auth_router.get("/reset-password", response_class=HTMLResponse)
async def simple_reset_password_page(request: Request):
    return templates.TemplateResponse(
        "auth/reset_password.html", {"request": request, "errors": {}}
    )


@auth_router.post("/reset-password")
async def simple_reset_password(
    request: Request,
    email: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user_svc = UserService(db)
    result = await user_svc.reset_password(email, new_password, confirm_password)
    if not result["success"]:
        return templates.TemplateResponse(
            "auth/reset_password.html",
            {
                "request": request,
                "errors": result["errors"],
                "email": email,
                "success": False,
            },
        )
    response = templates.TemplateResponse(
        "auth/reset_password.html",
        {
            "request": request,
            "success": True,
            "success_message": "Пароль успешно изменен!",
            "email": email,
        },
    )
    response.set_cookie(
        "access_token",
        result["access_token"],
        httponly=True,
        max_age=settings.MAX_AGE,
        secure=(settings.ENV == "production"),
        samesite="lax",
    )
    response.headers["Refresh"] = "3; url=/products"
    return response
