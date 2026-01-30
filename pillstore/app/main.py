from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.routers import products, users, orders, auth, profile, admin, errors, scraper
from app.api import api_products

from app.exceptions.products import include_product_exceptions

app = FastAPI(title="PillStore")

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")


@app.get("/")
async def redirect_to_docs():
    return RedirectResponse(url="/products")

app.include_router(scraper.router)
app.include_router(auth.auth_router)
app.include_router(api_products.router)
app.include_router(products.router)
app.include_router(users.router)
app.include_router(orders.router)
app.include_router(admin.router)
app.include_router(profile.router, prefix="/profile")
app.include_router(errors.router)


include_product_exceptions(app)
