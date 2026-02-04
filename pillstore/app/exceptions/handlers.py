from fastapi import FastAPI, Request
from app.core.config import templates


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


def setup_html_error_handlers(app: FastAPI):
    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError):
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
