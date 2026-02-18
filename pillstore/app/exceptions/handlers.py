from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.core.config import templates


class AuthException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class TokenExpiredError(AuthException):
    def __init__(self):
        super().__init__("Срок действия токена истек")


class InvalidCredentialsError(AuthException):
    def __init__(self):
        super().__init__("Не удалось подтвердить учетные данные")


class NotFoundError(Exception):
    def __init__(self, entity: str, id_or_slug: str | int):
        self.entity = entity
        self.id_or_slug = id_or_slug
        super().__init__(f"{entity} '{id_or_slug}' не найден")


class BusinessError(Exception):
    def __init__(self, entity: str, message: str):
        self.entity = entity
        self.message = message
        super().__init__(message)


class ProductNotFoundError(NotFoundError):
    def __init__(self, product_id: int):
        super().__init__("Товар", product_id)


class UserNotFoundError(NotFoundError):
    def __init__(self, user_id: int):
        super().__init__("Пользователь", user_id)


class OrderNotFoundError(NotFoundError):
    def __init__(self, order_id: int):
        super().__init__("Заказ", order_id)


class CartNotFoundError(NotFoundError):
    def __init__(self, cart_id: int):
        super().__init__("Корзина", cart_id)


def is_api_request(request: Request) -> bool:
    # Проверяем по пути
    if request.url.path.startswith("/api/"):
        return True

    # Проверяем по заголовку Accept
    accept_header = request.headers.get("accept", "")
    if "application/json" in accept_header:
        return True

    return False


def setup_html_error_handlers(app: FastAPI):  # noqa: C901
    @app.exception_handler(AuthException)
    async def auth_exception_handler(request: Request, exc: AuthException):
        if is_api_request(request):
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=exc.headers,
            )

        return templates.TemplateResponse(
            "errors/admin_error.html",
            {
                "request": request,
                "code": exc.status_code,
                "title": "Ошибка авторизации",
                "message": exc.detail,
                "tab": "dashboard",
            },
            status_code=exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if is_api_request(request):
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=exc.headers,
            )

        return templates.TemplateResponse(
            "errors/admin_error.html",
            {
                "request": request,
                "code": exc.status_code,
                "title": "Ошибка",
                "message": exc.detail,
                "tab": "dashboard",
            },
            status_code=exc.status_code,
        )

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError):
        if is_api_request(request):
            return JSONResponse(
                status_code=404,
                content={"detail": str(exc)},
            )

        context = {
            "request": request,
            "code": 404,
            "title": "Не найдено",
            "message": str(exc),
            "tab": "dashboard",
        }
        return templates.TemplateResponse(
            "errors/admin_error.html", context, status_code=404
        )

    @app.exception_handler(BusinessError)
    async def business_error_handler(request: Request, exc: BusinessError):
        if is_api_request(request):
            return JSONResponse(
                status_code=400,
                content={"detail": str(exc), "entity": exc.entity},
            )

        return templates.TemplateResponse(
            "errors/admin_error.html",
            {
                "request": request,
                "code": 400,
                "title": "Ошибка",
                "message": str(exc),
                "tab": "dashboard",
            },
            status_code=400,
        )

    @app.exception_handler(Exception)
    async def general_error_handler(request: Request, exc: Exception):
        if is_api_request(request):
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal Server Error"},
            )

        return templates.TemplateResponse(
            "errors/admin_error.html",
            {
                "request": request,
                "code": 500,
                "title": "Ошибка сервера",
                "message": "Что-то пошло не так",
                "tab": "dashboard",
            },
            status_code=500,
        )
