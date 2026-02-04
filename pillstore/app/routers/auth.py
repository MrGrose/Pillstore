from fastapi import APIRouter, Form, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db
from app.core.security import create_access_token
from app.core.config import templates
from app.services.user_service import UserService
from app.core.config import MAX_AGE


auth_router = APIRouter(prefix="/auth")


@auth_router.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("/auth/login.html", {"request": request})


@auth_router.post("/login")
async def login(
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user_svc = UserService(db)
    access_token = await user_svc.authenticate_user(email, password)
    response = RedirectResponse("/products", status_code=303)
    response.set_cookie("access_token", access_token, httponly=True, max_age=MAX_AGE)
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
    errors = await user_svc.validate_registration_data(email, password)
    if errors:
        return templates.TemplateResponse(
            "auth/register.html", {"request": request, "errors": errors}
        )
    user = await user_svc.register_user(email, password, role)
    access_token = create_access_token(
        {"sub": user.email, "role": user.role, "id": user.id}
    )
    response = RedirectResponse("/products?msg=registered", status_code=303)
    response.set_cookie("access_token", access_token, httponly=True, max_age=86400)
    return response
