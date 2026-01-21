from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

class ProductNotFoundError(Exception):
    def __init__(self, product_id: int):
        self.product_id = product_id

def include_product_exceptions(app: FastAPI) -> None:
    @app.exception_handler(ProductNotFoundError)
    async def product_not_found_handler(request: Request, exc: ProductNotFoundError):
        return JSONResponse(status_code=404, content={"detail": f"Товар {exc.product_id} не найден"})