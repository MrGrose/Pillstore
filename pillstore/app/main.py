from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.v2.admin import admin_router
from app.api.v2.auth import auth_router
from app.api.v2.cart import cart_router
from app.api.v2.categories import categories_router
from app.api.v2.favorites import favorites_router
from app.api.v2.orders import orders_router
from app.api.v2.products import product_router
from app.api.v2.profile import profile_router
from app.core.config import settings
from app.core.init import lifespan
from app.core.logger import LoggingMiddleware
from app.exceptions.handlers import setup_html_error_handlers
from app.routers import admin, auth, errors, orders, products, profile, scraper

tags_metadata = [
    {"name": "Health"},
    {"name": "API v2 Products"},
    {"name": "API v2 Categories"},
    {"name": "API v2 Auth"},
    {"name": "API v2 Cart"},
    {"name": "API v2 Orders"},
    {"name": "API v2 Profile"},
    {"name": "API v2 Admin"},
    {"name": "Products"},
    {"name": "Auth"},
    {"name": "Orders"},
    {"name": "Admin"},
    {"name": "Profile"},
    {"name": "Errors"},
    {"name": "Scraper"},
]

app = FastAPI(
    title="PillStore",
    description="Интернет-магазин продаж БАДов",
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=tags_metadata,
)

setup_html_error_handlers(app)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=settings.SESSION_MAX_AGE,
)

if settings.ENV == "production":
    app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(LoggingMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")


@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/products", status_code=302)


app.include_router(scraper.router, tags=["Scraper"])
app.include_router(auth.auth_router, tags=["Auth"])
app.include_router(products.router, tags=["Products"])
app.include_router(orders.router, tags=["Orders"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(profile.router, prefix="/profile", tags=["Profile"])
app.include_router(errors.router, tags=["Errors"])
app.include_router(product_router)
app.include_router(categories_router)
app.include_router(auth_router)
app.include_router(cart_router)
app.include_router(favorites_router)
app.include_router(orders_router)
app.include_router(profile_router)
app.include_router(admin_router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "pillstore": "ready"}
