from fastapi import APIRouter, Form, Depends, Request, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi.security import OAuth2PasswordRequestForm
from app.core.deps import get_db
from app.core.security import verify_password, create_access_token, hash_password
from app.models.users import User as UserModel
from app.core.config import templates

MAX_AGE = 86400

auth_router = APIRouter(prefix="/auth")

@auth_router.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("/auth/login.html", {"request": request})

@auth_router.post("/login")
async def login(
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    form_data = OAuth2PasswordRequestForm(username=email, password=password)
    result = await db.scalars(
        select(UserModel).where(
            UserModel.email == form_data.username, 
            UserModel.is_active.is_(True)
        )
    )
    user = result.first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role, "id": user.id}
    )
    
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
async def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
    role: str = Form("buyer"),
):
    errors: list[str] = []

    # Валидация
    if "@" not in email or not email.endswith((".com", ".ru", ".de")):
        errors.append("Некорректный email")
    if len(password) < 6:
        errors.append("Пароль не короче 6 символов")

    # Проверка уникальности
    existing = await db.scalars(select(UserModel).where(UserModel.email == email))
    if existing.first():
        errors.append("Email уже зарегистрирован")

    if errors:
        return templates.TemplateResponse(
            "auth/register.html", {"request": request, "errors": errors}
        )

    # Создание
    hashed_pw = hash_password(password)
    user = UserModel(email=email, hashed_password=hashed_pw, is_active=True, role=role)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Логин сразу после регистрации
    access_token = create_access_token({"sub": user.email, "role": user.role, "id": user.id})
    response = RedirectResponse("/products?msg=registered", status_code=303)
    response.set_cookie("access_token", access_token, httponly=True, max_age=86400)
    return response

